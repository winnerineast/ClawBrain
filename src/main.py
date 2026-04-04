# Generated from design/gateway.md v1.21
import httpx
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from src.adapters.ollama import OllamaAdapter
from src.adapters.openai import OpenAIAdapter
from src.adapters.lmstudio import LMStudioAdapter
from src.scout import ModelScout
from src.memory.router import MemoryRouter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化全局资源
    scout = ModelScout()
    app.state.memory_router = MemoryRouter()
    app.state.ollama_adapter = OllamaAdapter(scout)
    app.state.openai_adapter = OpenAIAdapter()
    app.state.lmstudio_adapter = LMStudioAdapter(scout)
    yield
    # 资源清理
    await app.state.ollama_adapter.close()
    await app.state.lmstudio_adapter.close()

app = FastAPI(title="ClawBrain Neural Gateway", lifespan=lifespan)

@app.post("/api/chat")
async def ollama_chat(request: Request):
    return await request.app.state.ollama_adapter.chat(request)

@app.get("/api/tags")
async def ollama_tags(request: Request):
    return await request.app.state.ollama_adapter.list_models()

@app.post("/v1/chat/completions")
async def v1_chat(request: Request):
    """
    统一 OpenAI 风格路由。
    """
    # 2.1 准则：精确异常处理
    try:
        raw_body = await request.body()
        if not raw_body:
            raise HTTPException(status_code=400, detail="Empty request body")
        body = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    model = body.get("model", "")
    
    # 路由逻辑不受 try-except 干扰，允许适配器抛出的 HTTPException 正常透传
    if model.startswith("lmstudio/"):
        return await request.app.state.lmstudio_adapter.chat(request)
    else:
        return await request.app.state.openai_adapter.chat(request)

@app.get("/health")
async def health():
    return {"status": "ok", "proxy": "ClawBrain", "providers": ["ollama", "lmstudio", "openai"]}
