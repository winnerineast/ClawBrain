# Generated from design/gateway.md v1.42 / design/context_engine_api.md v1.1
import json
import httpx
import logging
import os
import asyncio
from typing import List, Dict, Any, Optional, Tuple
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

# P27: Security blacklist - headers forbidden from upstream forwarding
INTERNAL_SENSITIVE_HEADERS = [
    "host", "content-length", "cookie", "set-cookie", "x-custom-sensitive",
    "connection", "upgrade", "proxy-connection", "keep-alive"
]

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

def prepare_upstream_headers(raw_headers: Dict[str, str], provider_config: Any, target_protocol: str) -> Dict[str, str]:
    """P27: Core Security - Implement L7 header isolation and Auth Dialect Alignment (Issue #1)"""
    upstream_headers = {}
    forbidden_prefixes = ("x-clawbrain-",)
    
    # 1. Mandatory blacklist filtering
    for k, v in raw_headers.items():
        kl = k.lower()
        if kl in INTERNAL_SENSITIVE_HEADERS or kl.startswith(forbidden_prefixes):
            continue
        upstream_headers[k] = v

    # 2. Auth isolation: strip all incoming generic credentials
    client_auth = upstream_headers.pop("Authorization", None) or upstream_headers.pop("authorization", None)
    client_x_key = upstream_headers.pop("x-api-key", None) or upstream_headers.pop("X-Api-Key", None)

    # 3. Protocol-specific re-injection
    if provider_config.api_key:
        # Scenario A: Static Override Mode
        if target_protocol == "anthropic":
            upstream_headers["x-api-key"] = provider_config.api_key
        elif target_protocol == "google":
            upstream_headers["x-goog-api-key"] = provider_config.api_key
        else:
            upstream_headers["Authorization"] = f"Bearer {provider_config.api_key}"
    else:
        # Scenario B: Transparent Relay Mode (Dialect Matching Required)
        if target_protocol == "anthropic":
            if client_x_key: upstream_headers["x-api-key"] = client_x_key
        elif target_protocol == "ollama":
            pass # Ollama local service ignores auth by default
        elif target_protocol in ["openai", "google", "mistral", "together"]:
            if client_auth: upstream_headers["Authorization"] = client_auth
            
    return upstream_headers

async def _process_request(request: Request):
    client: httpx.AsyncClient = request.app.state.http_client
    registry: ProviderRegistry = request.app.state.registry
    scout: ModelScout = request.app.state.scout
    memory_router: MemoryRouter = request.app.state.memory_router
    pipeline: Pipeline = request.app.state.pipeline

    try:
        raw_body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 1. Protocol Detection
    source_protocol, std_req = ProtocolDetector.detect_and_standardize(raw_body)
    context_id = request.headers.get("x-clawbrain-session", "default")
    
    # 2. Provider Resolution
    provider_name, provider_config = registry.resolve_provider(std_req.model)
    if not provider_config:
        logger.warning(f"[ROUTER] 501 Block: {std_req.model}")
        raise HTTPException(status_code=501, detail=f"Route for '{std_req.model}' is not configured.")

    target_protocol = provider_config.protocol
    
    # P27: Apply Security Filtering
    pass_headers = prepare_upstream_headers(dict(request.headers), provider_config, target_protocol)
    logger.info(f"[ADAPTER] Target: {provider_name} | Dialect: {target_protocol} | Headers Sanitized")

    # 3. Model Gating & Neural Augmentation
    tier = await scout.get_model_tier(std_req.model)
    if provider_name != "ollama": tier = ModelTier.TIER_1

    last_msg_content = std_req.messages[-1].content if std_req.messages else ""
    intent = pipeline.compressor.compress(last_msg_content)
    enriched_context = await memory_router.get_combined_context(context_id, intent)
    prominent_context = f"\n[IMPORTANT: PRIORITIZE THESE FACTS]\n{enriched_context}\n"
    std_req.messages.insert(0, Message(role="system", content=prominent_context))
    std_req = pipeline.run(std_req, tier)

    # 4. Dialect Translation
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

    # 5. Forwarding
    try:
        if std_req.stream:
            async def stream_generator():
                async with client.stream("POST", endpoint, json=target_payload, headers=pass_headers) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                # Fallback ingestion for Relay Mode
                await memory_router.ingest(raw_body, {"message": {"content": "[Streamed]"}}, context_id=context_id)
            return StreamingResponse(stream_generator())
        else:
            resp = await client.post(endpoint, json=target_payload, headers=pass_headers)
            resp_json = resp.json()
            await memory_router.ingest(raw_body, resp_json, context_id=context_id)
            return resp_json
    except Exception as e:
        logger.error(f"Forwarding error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/chat")
async def handle_ollama(request: Request): return await _process_request(request)

@app.post("/v1/chat/completions")
async def handle_openai(request: Request): return await _process_request(request)

@app.get("/health")
async def health(): return {"status": "ok", "mode": "Universal Neural Relay", "version": "1.42"}

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
    """3.1: Individual ingestion (legacy/heartbeat support)."""
    mr: MemoryRouter = request.app.state.memory_router
    if body.is_heartbeat: return {"trace_id": None, "ingested": False}
    payload = {"messages": [{"role": body.role, "content": body.content}]}
    trace_id = await mr.ingest(payload, context_id=body.session_id)
    return {"trace_id": trace_id, "ingested": True}

@app.post("/internal/assemble")
async def internal_assemble(body: Any, request: Request):
    """3.2: Context Assembly (Pre-model run)."""
    raw = await request.json()
    session_id = raw.get("session_id")
    focus = raw.get("current_focus") or ""
    mr: MemoryRouter = request.app.state.memory_router
    context = await mr.get_combined_context(session_id, focus)
    addition = f"[CLAWBRAIN MEMORY]\n{context}\n[END CLAWBRAIN MEMORY]" if context.strip() else ""
    return {"system_prompt_addition": addition, "chars_used": len(addition)}

@app.post("/internal/compact")
async def internal_compact(body: Any, request: Request):
    """3.3: Manual Compaction / Distillation."""
    raw = await request.json()
    session_id = raw.get("session_id")
    mr: MemoryRouter = request.app.state.memory_router
    rows = mr.hippo.get_recent_traces(limit=mr.distill_threshold, context_id=session_id)
    traces = []
    for row in rows:
        raw_c = row.get("raw_content") or mr.hippo.get_content(row["trace_id"])
        if raw_c:
            try: traces.append(json.loads(raw_c))
            except: pass
    if traces: await mr.neo.distill(session_id, traces)
    return {"ok": True, "compacted": True}

@app.post("/internal/after-turn")
async def internal_after_turn(body: AfterTurnRequest, request: Request):
    """
    3.4: Turn Settlement Center (v1.1) - Primary Ingestion Point for Issue #001.
    """
    mr: MemoryRouter = request.app.state.memory_router
    session_id = body.session_id
    new_msgs = body.new_messages
    
    if not new_msgs:
        # Mandatory audit log for empty turns
        logger.error(f"[INT_AFTER_TURN] Error: No new messages received for turn session={session_id}")
        return {"ok": True, "ingested_count": 0}

    # 1. Batch Ingestion: Pair User stimulus with Assistant reaction
    user_msg = next((m for m in reversed(new_msgs) if m.get("role") == "user"), None)
    assistant_msg = next((m for m in reversed(new_msgs) if m.get("role") == "assistant"), None)
    
    if user_msg:
        # Reconstruct Trace
        stimulus = {"messages": [user_msg]}
        reaction = {"message": assistant_msg} if assistant_msg else None
        trace_id = await mr.ingest(stimulus, reaction=reaction, context_id=session_id)
        logger.info(f"[INT_AFTER_TURN] Ingested Turn Trace | session={session_id} trace={trace_id}")

    # 2. State Solidification
    wm = mr._get_wm(session_id)
    mr.hippo.save_wm_state(session_id, wm.items)
    
    # 3. Distillation Counter
    mr._trace_counter += 1
    if mr._trace_counter >= mr.distill_threshold:
        asyncio.create_task(mr._auto_distill_worker(session_id))
        mr._trace_counter = 0
        
    return {"ok": True, "ingested_count": len(new_msgs)}
