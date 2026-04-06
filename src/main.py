# Generated from design/gateway.md v1.40 / design/config.md v1.0 / design/management_api.md v1.0 / design/context_engine_api.md v1.1
import json
import httpx
import logging
import os
import asyncio
from typing import List, Dict, Any, Optional
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
    
    # P27: 安全审计修复 - 实现 L7 协议头隔离 (Issue #1)
    pass_headers = {}
    forbidden_prefixes = ("x-clawbrain-",)
    forbidden_exact = ("host", "content-length", "cookie", "set-cookie", "x-custom-sensitive", "connection", "upgrade")
    
    for k, v in raw_headers.items():
        kl = k.lower()
        if kl in forbidden_exact or kl.startswith(forbidden_prefixes):
            continue
        pass_headers[k] = v

    # 鉴权头方言对齐：确保只转发匹配目标协议的鉴权
    client_auth = pass_headers.pop("Authorization", None) or pass_headers.pop("authorization", None)
    client_x_key = pass_headers.pop("x-api-key", None) or pass_headers.pop("X-Api-Key", None)

    try:
        raw_body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    source_protocol, std_req = ProtocolDetector.detect_and_standardize(raw_body)
    context_id = raw_headers.get("x-clawbrain-session", "default")
    
    provider_name, provider_config = registry.resolve_provider(std_req.model)
    if not provider_config:
        raise HTTPException(status_code=501, detail=f"Route for '{std_req.model}' is not configured.")

    target_protocol = provider_config.protocol
    
    # 重新注入合法鉴权
    if provider_config.api_key:
        if target_protocol == "anthropic": pass_headers["x-api-key"] = provider_config.api_key
        elif target_protocol == "google": pass_headers["x-goog-api-key"] = provider_config.api_key
        else: pass_headers["Authorization"] = f"Bearer {provider_config.api_key}"
    else:
        if target_protocol == "anthropic" and client_x_key: pass_headers["x-api-key"] = client_x_key
        elif target_protocol in ["openai", "google", "mistral", "together"] and client_auth:
            pass_headers["Authorization"] = client_auth
    
    logger.info(f"[ADAPTER] Target: {provider_name} | Dialect: {target_protocol} | Headers Sanitized")
    tier = await scout.get_model_tier(std_req.model)
    if provider_name != "ollama": tier = ModelTier.TIER_1

    # 4. 神经增强
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
                async with client.stream("POST", endpoint, json=target_payload, headers=pass_headers) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                # Relay 模式下的记忆捕获（兜底逻辑）
                await memory_router.ingest(raw_body, {"message": {"content": "[Streamed]"}}, context_id=context_id)
            return StreamingResponse(stream_generator())
        else:
            resp = await client.post(endpoint, json=target_payload, headers=pass_headers)
            resp_json = resp.json()
            await memory_router.ingest(raw_body, resp_json, context_id=context_id)
            return resp_json
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/chat")
async def handle_ollama(request: Request): return await _process_request(request)

@app.post("/v1/chat/completions")
async def handle_openai(request: Request): return await _process_request(request)

@app.get("/health")
async def health(): return {"status": "ok", "mode": "Universal Neural Relay", "version": "1.41"}

# ── P23 Context Engine Internal API (v1.1) ──────────────────────────────────

class IngestRequest(BaseModel):
    session_id: str
    role: str
    content: str
    is_heartbeat: bool = False

class AfterTurnRequest(BaseModel):
    session_id: str
    new_messages: List[Dict[str, Any]]

@app.post("/internal/ingest")
async def internal_ingest(body: IngestRequest, request: Request):
    """
    3.1 准则：单独存入（用于非 Turn 驱动场景）。
    """
    mr: MemoryRouter = request.app.state.memory_router
    if body.is_heartbeat:
        return {"trace_id": None, "ingested": False}
    
    payload = {"messages": [{"role": body.role, "content": body.content}]}
    trace_id = await mr.ingest(payload, context_id=body.session_id)
    return {"trace_id": trace_id, "ingested": True}

@app.post("/internal/assemble")
async def internal_assemble(body: Any, request: Request):
    """
    3.2 准则：装配上下文。
    """
    raw = await request.json()
    session_id = raw.get("session_id")
    focus = raw.get("current_focus") or ""
    token_budget = raw.get("token_budget") or 4096
    
    mr: MemoryRouter = request.app.state.memory_router
    max_chars = int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", "4000"))
    char_budget = min(token_budget * 3, max_chars)
    
    context = await mr.get_combined_context(session_id, focus)
    addition = f"[CLAWBRAIN MEMORY]\n{context}\n[END CLAWBRAIN MEMORY]" if context.strip() else ""
    
    logger.info(f"[INT_ASSEMBLE] session={session_id} chars={len(addition)}")
    return {
        "system_prompt_addition": addition,
        "chars_used": len(addition),
        "budget_chars": max_chars
    }

@app.post("/internal/compact")
async def internal_compact(body: Any, request: Request):
    """
    3.3 准则：手动/触发提纯。
    """
    raw = await request.json()
    session_id = raw.get("session_id")
    force = raw.get("force") or False
    
    mr: MemoryRouter = request.app.state.memory_router
    # 执行提纯
    rows = mr.hippo.get_recent_traces(limit=mr.distill_threshold, context_id=session_id)
    traces = []
    for row in rows:
        raw_c = row.get("raw_content") or mr.hippo.get_content(row["trace_id"])
        if raw_c:
            try: traces.append(json.loads(raw_c))
            except: pass
    
    if traces:
        await mr.neo.distill(session_id, traces)
    
    # 剪枝 WM
    keep_recent = int(os.getenv("CLAWBRAIN_WM_COMPACT_KEEP_RECENT", "5"))
    wm = mr._get_wm(session_id)
    pruned_count = max(0, len(wm.items) - keep_recent)
    wm.items = wm.items[-keep_recent:] if pruned_count > 0 else wm.items
    mr.hippo.save_wm_state(session_id, wm.items)
    
    logger.info(f"[INT_COMPACT] session={session_id} pruned={pruned_count}")
    return {"ok": True, "compacted": True, "wm_pruned": pruned_count}

@app.post("/internal/after-turn")
async def internal_after_turn(body: AfterTurnRequest, request: Request):
    """
    3.4 准则：Turn 结算中心 (v1.1)。
    核心修复：从 new_messages 中重建对话对并存入海马体。
    """
    mr: MemoryRouter = request.app.state.memory_router
    session_id = body.session_id
    new_msgs = body.new_messages

    if not new_msgs:
        # 3.4 准则：强制 Error 日志
        logger.error(f"[INT_AFTER_TURN] Error: No new messages received for turn session={session_id}")
        return {"ok": True, "ingested_count": 0}

    # 1. 对话配对采集逻辑
    user_msg = next((m for m in reversed(new_msgs) if m.get("role") == "user"), None)
    assistant_msg = next((m for m in reversed(new_msgs) if m.get("role") == "assistant"), None)
    
    if user_msg:
        # 重建迹线
        stimulus = {"messages": [user_msg]}
        reaction = {"message": assistant_msg} if assistant_msg else None
        trace_id = await mr.ingest(stimulus, reaction=reaction, context_id=session_id)
        logger.info(f"[INT_AFTER_TURN] Ingested Turn Trace | session={session_id} trace={trace_id}")

    # 2. 状态固化
    wm = mr._get_wm(session_id)
    mr.hippo.save_wm_state(session_id, wm.items)

    # 3. 提纯计数
    mr._trace_counter += 1
    if mr._trace_counter >= mr.distill_threshold:
        asyncio.create_task(mr._auto_distill_worker(session_id))
        mr._trace_counter = 0

    return {"ok": True, "ingested_count": len(new_msgs)}
