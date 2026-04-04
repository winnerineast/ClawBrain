# Generated from design/memory_integration.md v1.2
import json
import httpx
import logging
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 2.2 准则：生命周期内初始化记忆中枢
    app.state.scout = ModelScout()
    app.state.memory_router = MemoryRouter()
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

    # 1. 协议探测与标准化
    source_protocol, std_req = ProtocolDetector.detect_and_standardize(raw_body)

    # 2. 路由发现
    provider_name, provider_config = registry.resolve_provider(std_req.model)
    target_protocol = provider_config.protocol
    
    # 3. 准入审计
    tier = await scout.get_model_tier(std_req.model)
    if provider_name != "ollama": tier = ModelTier.TIER_1

    # 4. 神经增强 (2.2 准则：集成记忆与压缩)
    context_id = raw_headers.get("x-clawbrain-session", "default")
    last_msg_content = std_req.messages[-1].content if std_req.messages else ""
    intent = pipeline.compressor.compress(last_msg_content)
    
    # 合成增强上下文
    enriched_context = await memory_router.get_combined_context(context_id, intent)
    
    # 注入为首个 System 消息
    std_req.messages.insert(0, Message(role="system", content=enriched_context))
    
    # 执行流水线压缩与增强
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

    # 6. 转发与闭环存储 (2.2 准则：动态分流阈值)
    offload_threshold = 65536 # 假设默认窗口为 64k 的 10% 约为 6.5KB (测试演示用)
    
    try:
        if std_req.stream:
            async def stream_generator():
                async with client.stream("POST", endpoint, json=target_payload, headers=pass_headers) as resp:
                    if resp.is_error:
                        yield json.dumps({"error": f"Upstream Error {resp.status_code}"}).encode()
                        return
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                # 闭环存证
                await memory_router.ingest(raw_body, {"message": {"content": "[Streamed]"}}, offload_threshold)
            return StreamingResponse(stream_generator())
        else:
            resp = await client.post(endpoint, json=target_payload, headers=pass_headers)
            resp_json = resp.json()
            # 闭环存证
            await memory_router.ingest(raw_body, resp_json, offload_threshold)
            return resp_json

    except Exception as e:
        logging.error(f"Forwarding error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/chat")
async def ollama_ingress(request: Request): return await _process_request(request)

@app.post("/v1/chat/completions")
async def openai_ingress(request: Request): return await _process_request(request)

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "Universal Neural Relay", "integrated": True}
