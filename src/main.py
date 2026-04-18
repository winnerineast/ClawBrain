# Generated from design/gateway.md v1.42 / design/management_api.md v1.2 / GEMINI.md Rule 12
import json
import httpx
import logging
import os
import asyncio
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import StreamingResponse, HTMLResponse
from starlette.responses import Response

from src.scout import ModelScout, ModelTier
from src.memory.router import MemoryRouter
from src.gateway.registry import ProviderRegistry
from src.gateway.detector import ProtocolDetector
from src.gateway.translator import DialectTranslator
from src.pipeline import Pipeline
from src.models import Message
from mcp.server.sse import SseServerTransport
from src.mcp_server import create_mcp_server
from src.utils.dashboard_tpl import DASHBOARD_HTML

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("GATEWAY")

class EngineState(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"

INTERNAL_SENSITIVE_HEADERS = [
    "host", "content-length", "cookie", "set-cookie", "x-custom-sensitive",
    "connection", "upgrade", "proxy-connection", "keep-alive"
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Optimized lifespan: Ensures core memory engines are connected synchronously
    to avoid race conditions during regression tests.
    """
    app.state.engine_state = EngineState.INITIALIZING
    app.state.scout = ModelScout()
    app.state.registry = ProviderRegistry()
    app.state.pipeline = Pipeline()
    app.state.http_client = httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=100))
    
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_dir = os.getenv("CLAWBRAIN_DB_DIR", os.path.join(base_dir, "data"))
        
        distill_url = os.getenv("CLAWBRAIN_DISTILL_URL")
        distill_model = os.getenv("CLAWBRAIN_DISTILL_MODEL")
        distill_provider = os.getenv("CLAWBRAIN_DISTILL_PROVIDER")

        # P47: Deterministic Readiness - core engine init is now tracked
        app.state.memory_router = MemoryRouter(
            db_dir=db_dir,
            distill_url=distill_url,
            distill_model=distill_model,
            distill_provider=distill_provider
        )
        
        # Wait for the router's internal async init to complete
        await app.state.memory_router.wait_until_ready()
        
        app.state.mcp_server = create_mcp_server(app.state.memory_router)
        app.state.mcp_sse = SseServerTransport("messages")
        
        app.state.engine_state = EngineState.READY
        logger.info("[INIT] Cognitive plane fully stabilized. State: READY")
    except Exception as e:
        app.state.engine_state = EngineState.DEGRADED
        logger.error(f"[INIT] Cognitive plane initialization failed: {e}")

    yield
    
    if hasattr(app.state, "memory_router"):
        await app.state.memory_router.aclose()
    await app.state.http_client.aclose()

app = FastAPI(title="ClawBrain Universal Relay", lifespan=lifespan)

def check_ready(app: FastAPI):
    if app.state.engine_state != EngineState.READY:
        raise HTTPException(
            status_code=503, 
            detail=f"Memory engine is {app.state.engine_state.value}"
        )

def prepare_upstream_headers(raw_headers: Dict[str, str], provider_config: Any, target_protocol: str) -> Dict[str, str]:
    upstream_headers = {}
    for k, v in raw_headers.items():
        kl = k.lower()
        if kl in INTERNAL_SENSITIVE_HEADERS or kl.startswith("x-clawbrain-"):
            continue
        upstream_headers[k] = v

    client_auth = upstream_headers.pop("Authorization", None) or upstream_headers.pop("authorization", None)

    if provider_config.api_key:
        if target_protocol == "anthropic":
            upstream_headers["x-api-key"] = provider_config.api_key
        else:
            upstream_headers["Authorization"] = f"Bearer {provider_config.api_key}"
    elif client_auth:
        upstream_headers["Authorization"] = client_auth

    return upstream_headers

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.42", "engine": "ClawBrain (session_id unified)"}

# ── INTERNAL PLUGIN API ──

@app.post("/internal/ingest")
async def internal_ingest(request: Request):
    check_ready(request.app)
    body = await request.json()
    mr = request.app.state.memory_router
    session_id = body.get("session_id", "default")
    stimulus = {"messages": [{"role": body.get("role", "user"), "content": body.get("content", "")}]}
    trace_id = await mr.ingest(stimulus, session_id=session_id, sync_distill=False)
    return {"trace_id": trace_id, "ingested": True}

@app.post("/internal/assemble")
async def internal_assemble(request: Request):
    check_ready(request.app)
    body = await request.json()
    mr = request.app.state.memory_router
    session_id = body.get("session_id", "default")
    query = body.get("current_focus", "")
    budget = body.get("token_budget", 2000)
    
    addition = await mr.get_combined_context(session_id, query, max_chars=budget * 4)
    mr._last_injections[session_id] = {"stimulus": {"messages": [{"role": "system", "content": addition}]}}
    return {"system_prompt_addition": addition, "chars_used": len(addition)}

@app.post("/internal/compact")
async def internal_compact(request: Request):
    check_ready(request.app)
    body = await request.json()
    mr = request.app.state.memory_router
    session_id = body.get("session_id", "default")
    summary = await mr.distill_session(session_id)
    return {"ok": True, "compacted": True if summary else False}

@app.post("/internal/after-turn")
async def internal_after_turn(request: Request):
    return {"ok": True}

# ── MANAGEMENT API ──

@app.get("/v1/memory/{session_id}")
async def get_memory_state(session_id: str, request: Request):
    check_ready(request.app)
    mr = request.app.state.memory_router
    wm = mr._get_wm(session_id)
    return {
        "session_id": session_id,
        "neocortex_summary": mr.neo.get_summary(session_id),
        "working_memory_count": len(wm.items),
        "working_memory_preview": [item.content for item in wm.items[-3:]]
    }

@app.delete("/v1/memory/{session_id}")
async def clear_memory(session_id: str, request: Request):
    check_ready(request.app)
    mr = request.app.state.memory_router
    mr.neo.clear_summary(session_id)
    if session_id in mr._wm_sessions:
        del mr._wm_sessions[session_id]
    return {"status": "cleared", "session_id": session_id}

@app.get("/v1/management/sessions")
async def list_sessions(request: Request):
    check_ready(request.app)
    sids = request.app.state.memory_router.hippo.get_all_session_ids()
    return {"sessions": sids, "total": len(sids)}

@app.get("/v1/management/traces/{session_id}")
async def get_traces(session_id: str, request: Request, limit: int = 50):
    check_ready(request.app)
    traces = request.app.state.memory_router.hippo.get_recent_traces(limit=limit, session_id=session_id)
    return {"session_id": session_id, "traces": traces}

@app.get("/v1/management/last_injection/{session_id}")
async def get_last_injection(session_id: str, request: Request):
    check_ready(request.app)
    return {"payload": request.app.state.memory_router._last_injections.get(session_id)}

@app.get("/dashboard")
async def serve_dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)

# ── CORE RELAY ──

@app.post("/v1/ingest")
async def ingest_v1(request: Request):
    check_ready(request.app)
    body = await request.json()
    session_id = body.get("session_id", "default")
    mr = request.app.state.memory_router
    stimulus = {"messages": [{"role": "user", "content": body.get("content", "")}]}
    tid = await mr.ingest(stimulus, session_id=session_id)
    return {"trace_id": tid, "status": "ingested"}

@app.post("/{path:path}")
async def gateway_relay(path: str, request: Request):
    check_ready(request.app)
    mr, reg, pipe, hc = request.app.state.memory_router, request.app.state.registry, request.app.state.pipeline, request.app.state.http_client
    body = await request.json()
    session_id = request.headers.get("x-clawbrain-session", "default")
    
    # 1. Pre-flight Validation (Rule: No network ops before security checks)
    input_protocol = ProtocolDetector.detect(path, body)
    full_model_name = body.get("model", "")
    p_name, provider_config = reg.resolve_provider(full_model_name)
    
    if not provider_config:
        raise HTTPException(status_code=501, detail=f"No provider found for model: {full_model_name}")

    tier = await request.app.state.scout.get_model_tier(full_model_name)
    if tier == ModelTier.TIER_3 and "tools" in body:
        raise HTTPException(status_code=422, detail="TIER_3 models do not support tools via ClawBrain")

    # 2. Context Enrichment
    query = DialectTranslator.extract_query(input_protocol, body)
    context = await mr.get_combined_context(session_id, query)
    enriched_body = DialectTranslator.inject_context(input_protocol, body, context)
    mr._last_injections[session_id] = enriched_body
    
    # 3. Execution
    headers = prepare_upstream_headers(request.headers, provider_config, provider_config.protocol)
    trace_id = await mr.pre_turn_pending(body, session_id=session_id)
    url = f"{provider_config.base_url}/{path.lstrip('/')}"
    
    try:
        if body.get("stream", False):
            return StreamingResponse(
                pipe.stream_relay(hc, url, enriched_body, headers, session_id, mr, body, trace_id),
                media_type="text/event-stream"
            )
        else:
            resp = await hc.post(url, json=enriched_body, headers=headers)
            final_json = resp.json()
            await pipe.post_turn_solidification(final_json, input_protocol, session_id, mr, body, trace_id)
            return final_json
    except Exception as e:
        await mr.orphan_turn(trace_id, body, str(e), session_id=session_id)
        raise HTTPException(status_code=502, detail=str(e))

async def mcp_router(scope, receive, send):
    app, path = scope["app"], scope["path"]
    if app.state.engine_state != EngineState.READY: return
    if path == "/mcp/sse":
        async with app.state.mcp_sse.connect_sse(scope, receive, send) as (r_str, w_str):
            await app.state.mcp_server.run(r_str, w_str, app.state.mcp_server.create_initialization_options())
    elif path == "/mcp/messages": 
        await app.state.mcp_sse.handle_post_message(scope, receive, send)

app.mount("/mcp", mcp_router)
