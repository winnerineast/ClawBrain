# Generated from design/gateway.md v1.22
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化全局资源
    app.state.scout = ModelScout()
    app.state.memory_router = MemoryRouter()
    app.state.registry = ProviderRegistry()
    app.state.pipeline = Pipeline()
    # 统一连接池
    app.state.http_client = httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=100))
    yield
    await app.state.http_client.aclose()

app = FastAPI(title="ClawBrain Universal Gateway", lifespan=lifespan)

async def _process_request(request: Request, force_target_protocol: str = None):
    """
    通用处理管道 (Universal Pipeline)
    """
    client: httpx.AsyncClient = request.app.state.http_client
    registry: ProviderRegistry = request.app.state.registry
    scout: ModelScout = request.app.state.scout
    memory_router: MemoryRouter = request.app.state.memory_router
    pipeline: Pipeline = request.app.state.pipeline

    try:
        raw_body = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    # 1. 协议探测与标准化 (Detector)
    try:
        source_protocol, std_req = ProtocolDetector.detect_and_standardize(raw_body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. 路由发现 (Registry)
    provider_name, provider_config = registry.resolve_provider(std_req.model)
    target_protocol = force_target_protocol or provider_config.protocol
    
    print(f"[ROUTER] Target Provider: {provider_name} | Dialect: {target_protocol}")

    # 3. 准入审计 (Scout)
    try:
        tier = await scout.get_model_tier(std_req.model)
        # 对于云端模型默认放行
        if provider_name in ["openai", "deepseek", "lmstudio"]:
            tier = ModelTier.TIER_1
    except Exception:
        tier = ModelTier.TIER_1

    if tier == ModelTier.TIER_3 and std_req.tools:
        raise HTTPException(status_code=422, detail=f"Model {std_req.model} cannot handle tools.")

    # 4. 记忆增强与优化 (Memory & Pipeline)
    context_id = request.headers.get("x-clawbrain-session", "default")
    last_msg = std_req.messages[-1].content if std_req.messages else ""
    intent = pipeline.compressor.compress(last_msg)
    
    enriched_context = await memory_router.get_combined_context(context_id, intent)
    
    # 注入增强上下文
    from src.models import Message
    std_req.messages.insert(0, Message(role="system", content=enriched_context))
    
    # 内容压缩与指令增强
    for msg in std_req.messages[1:]:
        if msg.content:
            msg.content = pipeline.compressor.compress(msg.content)
    
    std_req = pipeline.enforcer.apply(std_req, tier)

    # 5. 方言翻译 (Translator)
    if target_protocol == "ollama":
        target_payload = DialectTranslator.to_ollama(std_req)
        endpoint = f"{provider_config.base_url}/api/chat"
    elif target_protocol == "openai":
        target_payload = DialectTranslator.to_openai(std_req)
        endpoint = f"{provider_config.base_url}/v1/chat/completions"
    else:
        raise HTTPException(status_code=501, detail="Target protocol not supported")

    # 6. 转发请求
    try:
        if std_req.stream:
            async def stream_generator():
                async with client.stream("POST", endpoint, json=target_payload) as resp:
                    if resp.is_error:
                        yield json.dumps({"error": f"Backend Error {resp.status_code}"}).encode()
                        return
                    
                    # 反向翻译流
                    if source_protocol == "openai" and target_protocol == "ollama":
                        async for sse_chunk in DialectTranslator.reverse_stream_ollama_to_openai(resp.aiter_bytes()):
                            yield sse_chunk.encode()
                    else:
                        async for chunk in resp.aiter_bytes():
                            yield chunk
                # 流结束，尝试异步保存（实际生产中应收集 chunk 进行解析）
                await memory_router.ingest(raw_body, {"message": {"content": "[Streamed Response]"}})

            # 根据源协议决定 Content-Type
            media_type = "text/event-stream" if source_protocol == "openai" else "application/x-ndjson"
            return StreamingResponse(stream_generator(), media_type=media_type)
        
        else:
            resp = await client.post(endpoint, json=target_payload)
            if resp.is_error:
                raise HTTPException(status_code=502, detail=f"Backend Error {resp.status_code}: {resp.text}")
            
            resp_json = resp.json()
            await memory_router.ingest(raw_body, resp_json)
            return resp_json

    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logging.error(f"Gateway Forwarding error: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/chat")
async def handle_ollama_ingress(request: Request):
    # Ollama 入口默认假定目标协议也是 ollama（如果 registry 没命中）
    return await _process_request(request)

@app.post("/v1/chat/completions")
async def handle_openai_ingress(request: Request):
    return await _process_request(request)

@app.get("/health")
async def health():
    return {"status": "ok", "proxy": "ClawBrain Universal"}
