# Generated from design/gateway.md v1.40 / design/config.md v1.0 / design/management_api.md v1.0 / design/context_engine_api.md v1.0
import json
import httpx
import logging
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from src.scout import ModelScout, ModelTier
from src.memory.router import MemoryRouter
from src.gateway.registry import ProviderRegistry
from src.gateway.detector import ProtocolDetector
from src.gateway.translator import DialectTranslator
from src.pipeline import Pipeline
from src.models import Message

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("GATEWAY")

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_dir = os.getenv("CLAWBRAIN_DB_DIR", "/home/nvidia/ClawBrain/data")
    app.state.scout = ModelScout()
    app.state.memory_router = MemoryRouter(db_dir=db_dir)
    app.state.registry = ProviderRegistry()
    app.state.pipeline = Pipeline()
    app.state.http_client = httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=100))
    yield
    await app.state.http_client.aclose()

app = FastAPI(title="ClawBrain Universal Relay", lifespan=lifespan)

async def _process_request(request: Request):
    client: httpx.AsyncClient = request.app.state.http_client
    registry: ProviderRegistry = request.app.state.registry
    scout: ModelScout = request.app.state.scout
    memory_router: MemoryRouter = request.app.state.memory_router
    pipeline: Pipeline = request.app.state.pipeline

    raw_headers = dict(request.headers)
    pass_headers = {k: v for k, v in raw_headers.items() if k.lower() not in ["host", "content-length"]}

    try:
        raw_body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 1. 协议探测
    source_protocol, std_req = ProtocolDetector.detect_and_standardize(raw_body)
    context_id = raw_headers.get("x-clawbrain-session", "default")
    if context_id == "default":
        logger.warning("[SESSION] No session header — using 'default'. Set 'x-clawbrain-session' for isolation.")
    logger.info(f"[DETECTOR] Proto: {source_protocol} | Model: {std_req.model}")

    # 2. 路由分发
    provider_name, provider_config = registry.resolve_provider(std_req.model)
    if not provider_config:
        logger.warning(f"[ROUTER] 501 Block: {std_req.model}")
        raise HTTPException(status_code=501, detail=f"Route for '{std_req.model}' is not configured.")

    target_protocol = provider_config.protocol
    logger.info(f"[ADAPTER] Target: {provider_name} | Dialect: {target_protocol}")

    # 3. 准入审计
    tier = await scout.get_model_tier(std_req.model)
    if provider_name != "ollama":
        tier = ModelTier.TIER_1

    is_tool_call = std_req.tools is not None and len(std_req.tools) > 0
    action = "BLOCK" if tier == ModelTier.TIER_3 and is_tool_call else "PASS"
    logger.info(f"[MODEL_QUAL] Tier: {tier.value} | Action: {action}")

    if action == "BLOCK":
        raise HTTPException(status_code=422, detail=f"Model {std_req.model} too small for tools.")

    # 4. 神经增强（带预算控制）
    last_msg_content = std_req.messages[-1].content if std_req.messages else ""
    intent = pipeline.compressor.compress(last_msg_content)
    enriched_context = await memory_router.get_combined_context(context_id, intent)
    prominent_context = f"\n[IMPORTANT: PRIORITIZE THESE FACTS]\n{enriched_context}\n"
    std_req.messages.insert(0, Message(role="system", content=prominent_context))
    std_req = pipeline.run(std_req, tier)

    # 5. 方言翻译
    if target_protocol == "ollama":
        target_payload = DialectTranslator.to_ollama(std_req)
        endpoint = f"{provider_config.base_url}/api/chat"
    elif target_protocol == "google":
        target_payload = DialectTranslator.to_google(std_req)
        model_id = std_req.model.split("/", 1)[1] if "/" in std_req.model else std_req.model
        endpoint = f"{provider_config.base_url}/v1beta/models/{model_id}:generateContent"
    elif target_protocol == "anthropic":
        target_payload = DialectTranslator.to_anthropic(std_req)
        endpoint = f"{provider_config.base_url}/v1/messages"
    else:
        target_payload = DialectTranslator.to_openai(std_req)
        endpoint = f"{provider_config.base_url}/v1/chat/completions"

    # 6. 转发
    try:
        if std_req.stream:
            async def stream_generator():
                collected_content = []
                async with client.stream("POST", endpoint, json=target_payload, headers=pass_headers) as resp:
                    if resp.is_error:
                        yield json.dumps({"error": f"Upstream Error {resp.status_code}"}).encode()
                        return
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                        # P15 流式记忆捕获：实时提取 assistant 内容
                        try:
                            text = chunk.decode('utf-8', errors='ignore').strip()
                            if text.startswith('data:'):
                                text = text[5:].strip()
                            if not text or text == '[DONE]':
                                continue
                            data = json.loads(text)
                            # Ollama 格式
                            if 'message' in data:
                                c = data['message'].get('content', '')
                                if c:
                                    collected_content.append(c)
                            # OpenAI SSE 格式
                            elif 'choices' in data:
                                for choice in data.get('choices', []):
                                    c = choice.get('delta', {}).get('content', '')
                                    if c:
                                        collected_content.append(c)
                        except:
                            pass
                reaction_content = ''.join(collected_content)
                await memory_router.ingest(
                    raw_body,
                    {'message': {'content': reaction_content or '[Streamed]'}},
                    context_id=context_id
                )
            return StreamingResponse(stream_generator())
        else:
            resp = await client.post(endpoint, json=target_payload, headers=pass_headers)
            try:
                resp_json = resp.json()
                await memory_router.ingest(raw_body, resp_json, context_id=context_id)
            except:
                pass
            if resp.is_error:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp_json
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Forwarding error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/chat")
async def handle_ollama(request: Request): return await _process_request(request)

@app.post("/v1/chat/completions")
async def handle_openai(request: Request): return await _process_request(request)

@app.get("/health")
async def health(): return {"status": "ok", "mode": "Universal Neural Relay", "version": "1.39"}

# ── P17 管理 API ────────────────────────────────────────────────────────────

@app.get("/v1/memory/{session_id}")
async def get_memory_state(session_id: str, request: Request):
    """查询指定 session 的记忆状态"""
    mr: MemoryRouter = request.app.state.memory_router
    summary = mr.neo.get_summary(session_id)
    active = mr._get_wm(session_id).get_active_contents()
    return {
        "session_id": session_id,
        "neocortex_summary": summary,
        "working_memory_count": len(active),
        "working_memory_preview": active[:3]
    }

@app.delete("/v1/memory/{session_id}")
async def clear_memory_session(session_id: str, request: Request):
    """清除指定 session 的新皮层摘要与工作记忆快照"""
    mr: MemoryRouter = request.app.state.memory_router
    mr.neo.clear_summary(session_id)
    mr.hippo.clear_wm_state(session_id)
    if session_id in mr._wm_sessions:
        del mr._wm_sessions[session_id]
    return {"status": "cleared", "session_id": session_id}

@app.post("/v1/memory/{session_id}/distill")
async def manual_distill(session_id: str, request: Request):
    """Manually trigger async Neocortex distillation for a session."""
    mr: MemoryRouter = request.app.state.memory_router
    asyncio.create_task(mr._auto_distill_worker(session_id))
    return {"status": "distillation_triggered", "session_id": session_id}


# ── P23 Context Engine Internal API ─────────────────────────────────────────
# These endpoints implement the four OpenClaw Context Engine lifecycle hooks.
# They are called by the @clawbrain/openclaw TypeScript plugin over localhost.
# Never expose these on a public network interface.

class IngestRequest(BaseModel):
    session_id: str
    role: str
    content: str
    is_heartbeat: bool = False

class AssembleRequest(BaseModel):
    session_id: str
    current_focus: str = ""
    token_budget: int = 4096

class CompactRequest(BaseModel):
    session_id: str
    force: bool = False

class AfterTurnRequest(BaseModel):
    session_id: str


@app.post("/internal/ingest")
async def internal_ingest(body: IngestRequest, request: Request):
    """
    Context Engine hook: ingest.
    Archive a single raw message into Hippocampus and update Working Memory.
    Heartbeat messages are silently skipped.
    """
    mr: MemoryRouter = request.app.state.memory_router

    if body.is_heartbeat:
        logger.debug(f"[INT_INGEST] Heartbeat skipped | session={body.session_id}")
        return {"trace_id": None, "ingested": False}

    payload = {"messages": [{"role": body.role, "content": body.content}]}
    trace_id = await mr.ingest(payload, context_id=body.session_id)
    logger.info(f"[INT_INGEST] session={body.session_id} role={body.role} trace={trace_id}")
    return {"trace_id": trace_id, "ingested": True}


@app.post("/internal/assemble")
async def internal_assemble(body: AssembleRequest, request: Request):
    """
    Context Engine hook: assemble.
    Query tri-layer memory and return a system_prompt_addition string.
    Always returns HTTP 200; empty memory yields an empty addition.
    """
    mr: MemoryRouter = request.app.state.memory_router

    # Rough heuristic: 1 token ≈ 3 chars; hard-cap by CLAWBRAIN_MAX_CONTEXT_CHARS
    max_chars = int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", "2000"))
    char_budget = min(body.token_budget * 3, max_chars)

    focus = body.current_focus or ""
    context = await mr.get_combined_context(body.session_id, focus)

    if context.strip():
        addition = (
            "[CLAWBRAIN MEMORY — injected by ClawBrain context engine]\n"
            f"{context}\n"
            "[END CLAWBRAIN MEMORY]"
        )
    else:
        addition = ""

    chars_used = len(addition)
    logger.info(
        f"[INT_ASSEMBLE] session={body.session_id} "
        f"chars_used={chars_used} budget={char_budget}"
    )
    return {
        "system_prompt_addition": addition,
        "chars_used": chars_used,
        "budget_chars": char_budget,
    }


@app.post("/internal/compact")
async def internal_compact(body: CompactRequest, request: Request):
    """
    Context Engine hook: compact (ownsCompaction=true).
    Distil recent traces into Neocortex and prune Working Memory.
    The session transcript cleanup is left to OpenClaw.
    """
    mr: MemoryRouter = request.app.state.memory_router
    keep_recent = int(os.getenv("CLAWBRAIN_WM_COMPACT_KEEP_RECENT", "5"))

    # Distil recent traces into Neocortex
    rows = mr.hippo.get_recent_traces(limit=mr.distill_threshold, context_id=body.session_id)
    traces = []
    for row in rows:
        raw = row.get("raw_content") or mr.hippo.get_content(row["trace_id"])
        if raw:
            try:
                traces.append(json.loads(raw))
            except Exception:
                pass

    if traces:
        await mr.neo.distill(body.session_id, traces)

    # Prune Working Memory to keep_recent most-recent items
    wm = mr._get_wm(body.session_id)
    if len(wm.items) > keep_recent:
        wm.items = sorted(wm.items, key=lambda x: x.timestamp)[-keep_recent:]
    mr.hippo.save_wm_state(body.session_id, wm.items)

    pruned = max(0, len(rows) - keep_recent)
    logger.info(
        f"[INT_COMPACT] session={body.session_id} "
        f"traces_distilled={len(traces)} wm_kept={len(wm.items)}"
    )
    return {
        "ok": True,
        "compacted": True,
        "traces_distilled": len(traces),
        "wm_pruned": pruned,
    }


@app.post("/internal/after-turn")
async def internal_after_turn(body: AfterTurnRequest, request: Request):
    """
    Context Engine hook: afterTurn.
    Persist Working Memory snapshot and optionally trigger background distillation.
    """
    mr: MemoryRouter = request.app.state.memory_router

    wm = mr._get_wm(body.session_id)
    mr.hippo.save_wm_state(body.session_id, wm.items)

    mr._trace_counter += 1
    if mr._trace_counter >= mr.distill_threshold:
        logger.info(
            f"[INT_AFTER_TURN] Distillation threshold reached — "
            f"spawning worker for session={body.session_id}"
        )
        asyncio.create_task(mr._auto_distill_worker(body.session_id))
        mr._trace_counter = 0

    logger.info(f"[INT_AFTER_TURN] session={body.session_id} wm_items={len(wm.items)}")
    return {"ok": True}
