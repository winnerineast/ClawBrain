# Generated from design/gateway.md v1.11
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from src.adapters.ollama import OllamaAdapter
from src.adapters.openai import OpenAIAdapter
from src.scout import ModelScout

app = FastAPI(title="ClawBrain Gateway")

# 初始化组件
scout = ModelScout()
ollama_adapter = OllamaAdapter(scout)
openai_adapter = OpenAIAdapter()

@app.post("/api/chat")
async def ollama_chat(request: Request):
    """Ollama 原生 Chat 接口路由"""
    return await ollama_adapter.chat(request)

@app.get("/api/tags")
async def ollama_tags():
    """Ollama 模型列表接口路由"""
    return await ollama_adapter.list_models()

@app.post("/v1/chat/completions")
async def openai_chat(request: Request):
    """OpenAI 原生 Chat 接口路由"""
    return await openai_adapter.chat(request)

@app.get("/health")
async def health():
    return {"status": "ok", "proxy": "ClawBrain"}
