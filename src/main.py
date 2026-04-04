# Generated from design/gateway.md v1.33
import json
import httpx
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
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

    # 1. 协议探测与元数据深度提取
    source_protocol, std_req = ProtocolDetector.detect_and_standardize(raw_body)
    context_id = raw_headers.get("x-clawbrain-session", "default")
    logger.info(f"[DETECTOR] Proto: {source_protocol} | Model: {std_req.model}")

    # 2. 严谨路由分发 (2.2 准则修正)
    provider_name, provider_config = registry.resolve_provider(std_req.model)
    if not provider_config:
        logger.warning(f"[ROUTER] 501 Block: {std_req.model}")
        raise HTTPException(status_code=501, detail=f"Route for '{std_req.model}' is not configured.")

    target_protocol = provider_config.protocol
    logger.info(f"[ADAPTER] Target: {provider_name} | Dialect: {target_protocol}")

    # 3. 准入审计
    tier = await scout.get_model_tier(std_req.model)
    if provider_name != "ollama": tier = ModelTier.TIER_1
    
    is_tool_call = std_req.tools is not None and len(std_req.tools) > 0
    action = "BLOCK" if tier == ModelTier.TIER_3 and is_tool_call else "PASS"
    logger.info(f"[MODEL_QUAL] Tier: {tier.value} | Action: {action}")

    if action == "BLOCK":
        raise HTTPException(status_code=422, detail=f"Model {std_req.model} too small for tools.")

    # 4. 神经增强 (2.4 准则：增强显著性)
    last_msg_content = std_req.messages[-1].content if std_req.messages else ""
    intent = pipeline.compressor.compress(last_msg_content)
    enriched_context = await memory_router.get_combined_context(context_id, intent)
    
    # 使用显著分隔符与指令加固记忆块
    prominent_context = f"\n[IMPORTANT: PRIORITIZE THESE FACTS]\n{enriched_context}\n"
    std_req.messages.insert(0, Message(role="system", content=prominent_context))
    
    std_req = pipeline.run(std_req, tier)

    # 5. 方言翻译
    if target_protocol == "ollama":
        target_payload = DialectTranslator.to_ollama(std_req)
        endpoint = f"{provider_config.base_url}/api/chat"
    elif target_protocol == "google":
        target_payload = DialectTranslator.to_google(std_req)
        model_name = std_req.model.split("/")[-1]
        endpoint = f"{provider_config.base_url}/v1beta/models/{model_name}:generateContent"
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
                await memory_router.ingest(raw_body, {"message": {"content": "[Streamed]"}})
            return StreamingResponse(stream_generator())
        else:
            resp = await client.post(endpoint, json=target_payload, headers=pass_headers)
            try:
                resp_json = resp.json()
                await memory_router.ingest(raw_body, resp_json)
            except: pass
            if resp.is_error:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp_json
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Forwarding error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/chat")
async def handle_ollama(request: Request): return await _process_request(request)

@app.post("/v1/chat/completions")
async def handle_openai(request: Request): return await _process_request(request)

@app.get("/health")
async def health(): return {"status": "ok", "mode": "Universal Neural Relay", "version": "1.33"}
