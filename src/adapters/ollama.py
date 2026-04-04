# Generated from design/gateway.md v1.11
import httpx
import json
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
from src.pipeline import Pipeline
from src.scout import ModelScout

class OllamaAdapter:
    def __init__(self, scout: ModelScout):
        self.base_url = "http://127.0.0.1:11434"
        self.pipeline = Pipeline()
        self.scout = scout

    async def chat(self, request: Request):
        try:
            body = await request.json()
            model_name = body.get("model")
            
            # 1. 准入审计 (Scout)
            tier = await self.scout.get_model_tier(model_name)
            
            # 2. 拦截检查 (Rule 2.2)
            if tier == "TIER_3_BASIC" and "tools" in body:
                raise HTTPException(status_code=422, detail=f"Model {model_name} too small for tool calling.")

            # 3. 提纯优化 (Pipeline)
            # 我们需要临时将 JSON 转为 Request 对象供 Pipeline 处理，处理完再转回 JSON
            # 这里为了保持原生性，我们只对 messages 列表进行内容压缩
            if "messages" in body:
                for msg in body["messages"]:
                    if "content" in msg and msg["content"]:
                        msg["content"] = self.pipeline.compressor.compress(msg["content"])
            
            # 4. 转发至真实后端
            async def stream_generator():
                async with httpx.AsyncClient(timeout=300.0) as client:
                    async with client.stream("POST", f"{self.base_url}/api/chat", json=body) as response:
                        async for chunk in response.aiter_bytes():
                            yield chunk

            if body.get("stream", False):
                return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
            else:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    resp = await client.post(f"{self.base_url}/api/chat", json=body)
                    return resp.json()

        except Exception as e:
            if isinstance(e, HTTPException): raise e
            raise HTTPException(status_code=502, detail=str(e))

    async def list_models(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            return resp.json()
