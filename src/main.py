# Generated from design/gateway.md v1.42 / design/interfaces_v2.md v2.0
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
from fastapi.responses import StreamingResponse
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

# P27: Security blacklist - headers forbidden from upstream forwarding
INTERNAL_SENSITIVE_HEADERS = [
    "host", "content-length", "cookie", "set-cookie", "x-custom-sensitive",
    "connection", "upgrade", "proxy-connection", "keep-alive"
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Optimized lifespan: Yields control to the server loop instantly.
    Initializations are pushed to background tasks to ensure <1s READY time.
    """
    app.state.engine_state = EngineState.INITIALIZING
    
    # 1. Immediate placeholder state
    app.state.scout = ModelScout()
    app.state.registry = ProviderRegistry()
    app.state.pipeline = Pipeline()
    app.state.http_client = httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=100))
    
    # 2. Asynchronous background initialization of the Memory Subsystem
    async def background_init():
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            default_db_dir = os.path.join(base_dir, "data")
            db_dir = os.getenv("CLAWBRAIN_DB_DIR", default_db_dir)
            
            distill_url = os.getenv("CLAWBRAIN_DISTILL_URL")
            distill_model = os.getenv("CLAWBRAIN_DISTILL_MODEL")
            distill_provider = os.getenv("CLAWBRAIN_DISTILL_PROVIDER")
            disable_rooms = os.getenv("CLAWBRAIN_DISABLE_ROOM_DETECTION", "false").lower() == "true"

            app.state.memory_router = MemoryRouter(
                db_dir=db_dir,
                distill_url=distill_url,
                distill_model=distill_model,
                distill_provider=distill_provider,
                enable_room_detection=not disable_rooms
            )
            
            # Initialize MCP after Router is ready
            app.state.mcp_server = create_mcp_server(app.state.memory_router)
            app.state.mcp_sse = SseServerTransport("messages")
            
            # Transition to READY
            app.state.engine_state = EngineState.READY
            logger.info("[INIT] Cognitive plane fully stabilized. State: READY")
        except Exception as e:
            app.state.engine_state = EngineState.DEGRADED
            logger.error(f"[INIT] Cognitive plane initialization failed: {e}")

    init_task = asyncio.create_task(background_init())
    
    yield
    
    # Cleanup
    init_task.cancel()
    if hasattr(app.state, "memory_router"):
        await app.state.memory_router.aclose()
    await app.state.http_client.aclose()

app = FastAPI(title="ClawBrain Universal Relay", lifespan=lifespan)

# --- READINESS HELPERS ---
def check_ready(app: FastAPI):
    if app.state.engine_state != EngineState.READY:
        raise HTTPException(
            status_code=503, 
            detail=f"Memory engine is {app.state.engine_state.value}"
        )

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
        elif target_protocol == "google":
            if client_x_key: upstream_headers["x-goog-api-key"] = client_x_key
        else:
            if client_auth: upstream_headers["Authorization"] = client_auth

    return upstream_headers

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.42",
        "engine": "ClawBrain Universal Relay (ChromaDB Enhanced)"
    }

# ── MANAGEMENT API ──

@app.get("/v1/memory/{session_id}")
async def get_memory_state(session_id: str, request: Request):
    check_ready(request.app)
    mr = request.app.state.memory_router
    wm = mr._get_wm(session_id)
    return {
        "session_id": session_id,
        "wm_count": len(wm.items),
        "recent_facts": [item.content for item in wm.items[-5:]],
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

@app.post("/v1/memory/{session_id}/distill")
async def trigger_manual_distill(session_id: str, request: Request):
    check_ready(request.app)
    mr = request.app.state.memory_router
    asyncio.create_task(mr._auto_distill_worker(session_id))
    return {"status": "distillation_triggered", "session_id": session_id}

@app.get("/v1/management/sessions")
async def list_sessions(request: Request):
    check_ready(request.app)
    mr = request.app.state.memory_router
    sids = mr.hippo.get_all_session_ids()
    return {"sessions": sids, "total": len(sids)}

@app.get("/v1/management/traces/{session_id}")
async def get_traces(session_id: str, request: Request, limit: int = 50):
    check_ready(request.app)
    mr = request.app.state.memory_router
    traces = mr.hippo.get_recent_traces(limit=limit, context_id=session_id)
    return {"session_id": session_id, "traces": traces}

@app.get("/dashboard")
async def serve_dashboard():
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=DASHBOARD_HTML)

@app.post("/v1/ingest")
async def ingest_memory(request: Request):
    """Universal Ingest API for CLI and MCP."""
    check_ready(request.app)
    body = await request.json()
    session_id = body.get("session_id", "default")
    content = body.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="Missing content")
    
    mr = request.app.state.memory_router
    stimulus = {"messages": [{"role": "user", "content": content}]}
    trace_id = await mr.ingest(stimulus, context_id=session_id, sync_distill=False)
    return {"trace_id": trace_id, "session_id": session_id}

@app.post("/v1/query")
async def query_memory(request: Request):
    """Universal Query API for CLI and MCP."""
    check_ready(request.app)
    body = await request.json()
    session_id = body.get("session_id", "default")
    query = body.get("query", "")
    budget = body.get("budget", 2000)
    
    mr = request.app.state.memory_router
    context = await mr.get_combined_context(session_id, query, max_chars=budget)
    return {"context": context, "session_id": session_id}

@app.get("/v1/status")
async def get_system_status(request: Request):
    """System health and memory engine stats."""
    if request.app.state.engine_state != EngineState.READY:
        return {"status": request.app.state.engine_state.value, "message": "Engine is warming up"}
    
    mr = request.app.state.memory_router
    return {
        "status": "online",
        "db_dir": mr.db_dir,
        "active_sessions": list(mr._wm_sessions.keys()),
        "vault_enabled": mr.vault_path is not None,
        "vault_path": mr.vault_path
    }

async def mcp_router(scope, receive, send):
    """Unified ASGI router for MCP SSE and Messages."""
    app = scope["app"]
    path = scope["path"]
    
    if app.state.engine_state != EngineState.READY:
        await send({"type": "http.response.start", "status": 503, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": f"MCP server is {app.state.engine_state.value}".encode()})
        return

    if path == "/mcp/sse":
        async with app.state.mcp_sse.connect_sse(scope, receive, send) as (read_stream, write_stream):
            await app.state.mcp_server.run(read_stream, write_stream, app.state.mcp_server.create_initialization_options())
    elif path == "/mcp/messages":
        await app.state.mcp_sse.handle_post_message(scope, receive, send)
    else:
        await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"Not Found"})

app.mount("/mcp", mcp_router)

# ── CATCH-ALL GATEWAY RELAY ──

@app.post("/{path:path}")
async def gateway_relay(path: str, request: Request):
    check_ready(request.app)
    mr = request.app.state.memory_router
    registry = request.app.state.registry
    pipeline = request.app.state.pipeline
    http_client = request.app.state.http_client
    
    body = await request.json()
    session_id = request.headers.get("x-clawbrain-session", "default")
    
    logger.info(f"[GATEWAY] Incoming request | session={session_id} path={path}")
    
    input_protocol = ProtocolDetector.detect(path, body)
    
    # 2. Model-based Routing Security
    full_model_name = body.get("model", "")
    p_name, provider_config = registry.resolve_provider(full_model_name)
    
    if not provider_config:
        logger.error(f"[GATEWAY] No provider found for model: {full_model_name}")
        raise HTTPException(status_code=501, detail=f"No provider configured for model: {full_model_name}")

    tier = await request.app.state.scout.get_model_tier(full_model_name)
    if tier == ModelTier.TIER_3 and "tools" in body:
        raise HTTPException(status_code=422, detail="TIER_3 models do not support tools via ClawBrain")

    target_protocol = provider_config.protocol
    target_url = f"{provider_config.base_url}/{path.lstrip('/')}"
    
    # 3. Context Enrichment (Semantic Recall)
    query = DialectTranslator.extract_query(input_protocol, body)
    context = await mr.get_combined_context(session_id, query)
    
    enriched_body = DialectTranslator.inject_context(input_protocol, body, context)
    
    # 4. Header Preparation
    upstream_headers = prepare_upstream_headers(request.headers, provider_config, target_protocol)
    
    # 4.5. Phase 38: Create PENDING trace (Issue #17)
    trace_id = await mr.pre_turn_pending(body, context_id=session_id)
    
    # 5. Forwarding
    try:
        if body.get("stream", False):
            # Stream Relay
            return StreamingResponse(
                pipeline.stream_relay(http_client, target_url, enriched_body, upstream_headers, session_id, mr, body, trace_id),
                media_type="text/event-stream"
            )
        else:
            # Atomic Relay
            resp = await http_client.post(target_url, json=enriched_body, headers=upstream_headers)
            final_json = resp.json()
            
            # Passive Archival (Solidification)
            await pipeline.post_turn_solidification(final_json, input_protocol, session_id, mr, body, trace_id)
            
            return final_json
            
    except Exception as e:
        logger.error(f"Forwarding error: {e}")
        await mr.orphan_turn(trace_id, body, str(e), context_id=session_id)
        raise HTTPException(status_code=502, detail=str(e))
