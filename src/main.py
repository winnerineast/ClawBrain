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
    # Dynamic default path for portability (Issue-003)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_db_dir = os.path.join(base_dir, "data")
    db_dir = os.getenv("CLAWBRAIN_DB_DIR", default_db_dir)
    
    app.state.scout = ModelScout()
    
    # ISSUE-004: Pass distillation config from env
    distill_url = os.getenv("CLAWBRAIN_DISTILL_URL")
    distill_model = os.getenv("CLAWBRAIN_DISTILL_MODEL")
    distill_provider = os.getenv("CLAWBRAIN_DISTILL_PROVIDER")
    
    # Phase 34: Support disabling room detection for tests/low-resource
    disable_rooms = os.getenv("CLAWBRAIN_DISABLE_ROOM_DETECTION", "false").lower() == "true"
    
    app.state.memory_router = MemoryRouter(
        db_dir=db_dir,
        distill_url=distill_url,
        distill_model=distill_model,
        distill_provider=distill_provider,
        enable_room_detection=not disable_rooms
    )
    
    logger.info(f"[INIT] Distillation Backend: {app.state.memory_router.neo.distill_provider} | URL: {app.state.memory_router.neo.distill_url}")
    
    app.state.registry = ProviderRegistry()
    app.state.pipeline = Pipeline()
    app.state.http_client = httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=100))
    yield
    await app.state.memory_router.aclose()
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

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "1.42",
        "engine": "ClawBrain Universal Relay (ChromaDB Enhanced)"
    }

# ── INTERNAL ENDPOINTS (Must be before catch-all) ──

@app.post("/internal/ingest")
async def internal_ingest(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "default")
    role = body.get("role", "user")
    content = body.get("content", "")
    sync = body.get("sync", False)
    is_heartbeat = body.get("is_heartbeat", False)
    
    if is_heartbeat:
        return {"trace_id": None, "ingested": False}
        
    mr = request.app.state.memory_router
    
    # Reconstruct Trace
    stimulus = {"messages": [{"role": role, "content": content}]}
    trace_id = await mr. ingest(stimulus, context_id=session_id, sync_distill=sync)
    
    return {"trace_id": trace_id, "ingested": True}

@app.post("/internal/assemble")
async def internal_assemble(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "default")
    current_focus = body.get("current_focus", "")
    token_budget = body.get("token_budget", 2000)
    
    mr = request.app.state.memory_router
    
    context = await mr.get_combined_context(session_id, current_focus, max_chars=token_budget)
    
    return {
        "system_prompt_addition": context,
        "chars_used": len(context),
        "budget_chars": token_budget
    }

@app.post("/internal/compact")
async def internal_compact(request: Request):
    """P23: Management - Manually trigger distillation and WM pruning."""
    body = await request.json()
    session_id = body.get("session_id", "default")
    force = body.get("force", False)
    
    mr = request.app.state.memory_router
    
    # Prune WM logic (simplified for compact)
    keep_recent = int(os.getenv("CLAWBRAIN_WM_COMPACT_KEEP_RECENT", "5"))
    wm = mr._get_wm(session_id)
    if len(wm.items) > keep_recent or force:
        asyncio.create_task(mr._auto_distill_worker(session_id))
        # Keep recent items
        wm.items = wm.items[-keep_recent:] if len(wm.items) > keep_recent else wm.items
        return {"ok": True, "compacted": True, "session_id": session_id}
        
    return {"ok": True, "compacted": False, "session_id": session_id}

class AfterTurnBody(BaseModel):
    session_id: str
    new_messages: List[Dict[str, Any]]
    sync: bool = False

@app.post("/internal/after-turn")
async def internal_after_turn(request: Request, body: AfterTurnBody):
    """P25: OpenClaw Loopback - Update L1 WM and L2 Archive after a full turn completes."""
    session_id = body.session_id
    new_msgs = body.new_messages
    mr = request.app.state.memory_router
    
    # 1. Batch Ingestion: Pair User stimulus with Assistant reaction
    user_msg = next((m for m in reversed(new_msgs) if m.get("role") == "user"), None)
    assistant_msg = next((m for m in reversed(new_msgs) if m.get("role") == "assistant"), None)
    
    if user_msg:
        # Reconstruct Trace
        stimulus = {"messages": [user_msg]}
        reaction = {"message": assistant_msg} if assistant_msg else None
        trace_id = await mr.ingest(stimulus, reaction=reaction, context_id=session_id, sync_distill=body.sync)
        logger.info(f"[INT_AFTER_TURN] Ingested Turn Trace | session={session_id} trace={trace_id}")

    # 2. State Solidification (L1 WM Snapshot)
    wm = mr._get_wm(session_id)
    mr.hippo.save_wm_state(session_id, wm.items)
    
    return {"ok": True, "ingested_count": len(new_msgs)}

# ── MANAGEMENT API (Must be before catch-all) ──

@app.get("/v1/memory/{session_id}")
async def get_memory_state(session_id: str, request: Request):
    mr = request.app.state.memory_router
    wm = mr._get_wm(session_id)
    summary = mr.neo.get_summary(session_id)
    
    return {
        "session_id": session_id,
        "neocortex_summary": summary,
        "working_memory_count": len(wm.items),
        "working_memory_preview": wm.get_active_contents()
    }

@app.delete("/v1/memory/{session_id}")
async def clear_memory_session(session_id: str, request: Request):
    mr = request.app.state.memory_router
    mr.hippo.clear_wm_state(session_id)
    mr.neo.clear_summary(session_id)
    if session_id in mr._wm_sessions:
        del mr._wm_sessions[session_id]
    return {"status": "cleared", "session_id": session_id}

@app.post("/v1/memory/{session_id}/distill")
async def trigger_manual_distill(session_id: str, request: Request):
    mr = request.app.state.memory_router
    asyncio.create_task(mr._auto_distill_worker(session_id))
    return {"status": "distillation_triggered", "session_id": session_id}

# ── CATCH-ALL GATEWAY RELAY ──

@app.post("/{path:path}")
async def gateway_relay(path: str, request: Request):
    mr = request.app.state.memory_router
    registry = request.app.state.registry
    pipeline = request.app.state.pipeline
    http_client = request.app.state.http_client
    
    # 1. Detect Input Protocol & Session
    body = await request.json()
    headers = dict(request.headers)
    session_id = headers.get("x-clawbrain-session", "default")
    logger.info(f"[GATEWAY] Incoming request | session={session_id} path={path}")
    
    input_protocol = ProtocolDetector.detect(path, body)
    
    # 2. Model-based Routing Security (P16 + Bug 11)
    full_model_name = body.get("model", "")
    
    # §2.4 Qualification Interception (Phase 24/25)
    # TIER_3 models do not support tools/function calling yet in ClawBrain.
    scout = request.app.state.scout
    tier = await scout.get_model_tier(full_model_name)
    if tier == ModelTier.TIER_3 and body.get("tools"):
        logger.warning(f"[GATEWAY] Blocked TIER_3 model {full_model_name} with tools.")
        raise HTTPException(status_code=422, detail="ClawBrain currently does not support tool calling for TIER_3 models.")

    provider_name, provider_config = registry.resolve_provider(full_model_name)
    
    if not provider_config:
        # P12: Strict OpenAI routing security - block unauthorized models
        if input_protocol == "openai":
             logger.warning(f"[GATEWAY] Blocked unauthorized OpenAI model: {full_model_name}")
             raise HTTPException(status_code=501, detail=f"Model {full_model_name} is not authorized for OpenAI relay.")
             
        # Fallback to path-based default if no model match (for local test setups)
        provider_config = registry.get_provider(input_protocol)
        target_protocol = provider_config.protocol
    else:
        target_protocol = provider_config.protocol
        # Apply prefix stripping if needed (Standard for ClawBrain routing)
        if "/" in full_model_name and provider_name in full_model_name:
             body["model"] = full_model_name.split("/", 1)[1]

    # 3. Context Injection (Phase 32 Sequential Gate)
    user_query = DialectTranslator.extract_query(input_protocol, body)
    context_budget = int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", "2000"))
    
    enriched_context = await mr.get_combined_context(session_id, user_query, max_chars=context_budget)
    
    # Apply Dialect Injection
    body = DialectTranslator.inject_context(input_protocol, body, enriched_context)
    
    # 4. Upstream Forwarding
    upstream_url = f"{provider_config.base_url}/{path.lstrip('/')}"
    upstream_headers = prepare_upstream_headers(headers, provider_config, target_protocol)
    
    # Phase 32: Sequential response handling
    is_stream = body.get("stream", False)
    
    try:
        if is_stream:
            return StreamingResponse(
                pipeline.stream_relay(http_client, upstream_url, body, upstream_headers, session_id, mr),
                media_type="text/event-stream"
            )
        else:
            resp = await http_client.post(upstream_url, json=body, headers=upstream_headers)
            resp.raise_for_status()
            final_json = resp.json()
            
            # Post-turn analysis (L1 charge + L2 archive)
            # Phase 25: We pass the original body (stimulus) to allow archival
            await pipeline.post_turn_solidification(final_json, input_protocol, session_id, mr, body)
            
            return final_json
            
    except Exception as e:
        logger.error(f"Forwarding error: {e}")
        raise HTTPException(status_code=502, detail=str(e))
