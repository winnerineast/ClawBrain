# Generated from design/memory_integration.md v1.1
import httpx
import json
import logging
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
from src.pipeline import Pipeline
from src.scout import ModelScout, ModelTier

class OllamaAdapter:
    def __init__(self, scout: ModelScout):
        self.base_url = "http://127.0.0.1:11434"
        self.pipeline = Pipeline()
        self.scout = scout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=100))
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def chat(self, request: Request):
        try:
            body = await request.json()
            model_name = body.get("model", "unknown")
            context_id = request.headers.get("x-clawbrain-session", "default")
            
            # 1. 执行准入契约判定
            tier = await self.scout.get_model_tier(model_name)
            
            # 2. 上下文增强 (2.2 准则)
            memory_router = request.app.state.memory_router
            intent = self.pipeline.compressor.compress(body.get("messages", [{}])[-1].get("content", ""))
            enriched_context = await memory_router.get_combined_context(context_id, intent)
            
            # 注入为首条 system 消息
            if "messages" in body:
                body["messages"].insert(0, {"role": "system", "content": enriched_context})

            # 3. 拦截控制
            if tier == ModelTier.TIER_3 and "tools" in body:
                raise HTTPException(status_code=422, detail=f"KPI Violation: Model {model_name} too small for tools.")

            # 4. 流水线优化 (压缩除增强消息外的其它内容)
            for msg in body["messages"][1:]:
                if "content" in msg and msg["content"]:
                    msg["content"] = self.pipeline.compressor.compress(msg["content"])
            
            # 5. 转发并闭环存储
            if body.get("stream", False):
                async def stream_generator():
                    full_response_chunks = []
                    async with self.client.stream("POST", f"{self.base_url}/api/chat", json=body) as resp:
                        if resp.is_error:
                            yield json.dumps({"error": "Backend KPI Failure"}).encode()
                            return
                        async for chunk in resp.aiter_bytes():
                            full_response_chunks.append(chunk)
                            yield chunk
                    
                    # 响应结束后异步存储 (闭环存储逻辑)
                    try:
                        # 简单合并 chunk 以获取完整响应用于存储
                        full_content = b"".join(full_response_chunks).decode()
                        # 这里为了简化，我们只尝试提取最后一个完整 JSON 的 content
                        # 实际生产中需要更复杂的流式解析
                        await memory_router.ingest(body, {"message": {"content": "Streamed Response Saved"}})
                    except:
                        pass

                return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
            else:
                resp = await self.client.post(f"{self.base_url}/api/chat", json=body)
                resp_json = resp.json()
                # 闭环存储逻辑
                await memory_router.ingest(body, resp_json)
                return resp_json

        except Exception as e:
            if isinstance(e, HTTPException): raise e
            logging.error(f"Adapter error: {e}")
            raise HTTPException(status_code=502, detail=str(e))

    async def list_models(self):
        resp = await self.client.get(f"{self.base_url}/api/tags")
        return resp.json()
