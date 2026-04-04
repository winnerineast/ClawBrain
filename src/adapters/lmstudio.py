# Generated from design/gateway.md v1.20
import httpx
import json
import logging
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
from src.pipeline import Pipeline
from src.scout import ModelScout, ModelTier

class LMStudioAdapter:
    """
    LM Studio 适配器。
    对接本地 1234 端口，兼容 OpenAI 协议。
    """
    def __init__(self, scout: ModelScout):
        self.base_url = "http://127.0.0.1:1234"
        self.pipeline = Pipeline()
        self.scout = scout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=50))
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def chat(self, request: Request):
        try:
            body = await request.json()
            model_full_name = body.get("model", "unknown")
            # 移除前缀以便转发给后端
            model_name = model_full_name.replace("lmstudio/", "")
            body["model"] = model_name
            
            context_id = request.headers.get("x-clawbrain-session", "default")
            
            # 1. 准入审计 (LM Studio 暂视为 TIER_1 以确保兼容，除非明确配置)
            tier = ModelTier.TIER_1 

            # 2. 上下文增强
            memory_router = request.app.state.memory_router
            last_msg = body.get("messages", [{}])[-1].get("content", "")
            intent = self.pipeline.compressor.compress(last_msg)
            enriched_context = await memory_router.get_combined_context(context_id, intent)
            
            # 注入系统消息
            if "messages" in body:
                body["messages"].insert(0, {"role": "system", "content": enriched_context})

            # 3. 内容优化
            for msg in body["messages"][1:]:
                if "content" in msg and msg["content"]:
                    msg["content"] = self.pipeline.compressor.compress(msg["content"])
            
            # 4. 转发
            print(f"[GATEWAY] Routing to LMStudio: {model_name}")
            
            if body.get("stream", False):
                async def stream_generator():
                    async with self.client.stream("POST", f"{self.base_url}/v1/chat/completions", json=body) as resp:
                        if resp.is_error:
                            yield json.dumps({"error": "LM Studio Backend Error"}).encode()
                            return
                        async for chunk in resp.aiter_bytes():
                            yield chunk
                    # 闭环存证
                    await memory_router.ingest(body, {"message": {"content": "LMStudio Streamed Response"}})
                
                return StreamingResponse(stream_generator(), media_type="text/event-stream")
            else:
                resp = await self.client.post(f"{self.base_url}/v1/chat/completions", json=body)
                resp_json = resp.json()
                # 闭环存储
                await memory_router.ingest(body, resp_json)
                return resp_json

        except Exception as e:
            logging.error(f"LMStudio Adapter error: {e}")
            raise HTTPException(status_code=502, detail=str(e))
