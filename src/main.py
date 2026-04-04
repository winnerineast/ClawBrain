# Generated from design/memory_integration.md v1.1
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from src.adapters.ollama import OllamaAdapter
from src.adapters.openai import OpenAIAdapter
from src.scout import ModelScout
from src.memory.router import MemoryRouter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 2.3 准则：在生命周期中初始化记忆路由器
    scout = ModelScout()
    app.state.memory_router = MemoryRouter()
    app.state.ollama_adapter = OllamaAdapter(scout)
    app.state.openai_adapter = OpenAIAdapter()
    yield
    # 资源清理
    await app.state.ollama_adapter.close()

app = FastAPI(title="ClawBrain Gateway", lifespan=lifespan)

@app.post("/api/chat")
async def ollama_chat(request: Request):
    return await request.app.state.ollama_adapter.chat(request)

@app.get("/api/tags")
async def ollama_tags(request: Request):
    return await request.app.state.ollama_adapter.list_models()

@app.post("/v1/chat/completions")
async def openai_chat(request: Request):
    return await request.app.state.openai_adapter.chat(request)

@app.get("/health")
async def health():
    return {"status": "ok", "proxy": "ClawBrain", "memory_engine": "ready"}
