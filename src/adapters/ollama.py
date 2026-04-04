# Generated from design/gateway.md v1.15
import httpx
import json
import logging
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
from src.pipeline import Pipeline
from src.scout import ModelScout

class OllamaAdapter:
    def __init__(self, scout: ModelScout):
        self.base_url = "http://127.0.0.1:11434"
        self.pipeline = Pipeline()
        self.scout = scout
        # 延迟初始化 client 池
        self._client = None

    @property
    def client(self):
        if self._client is None:
            # 2.4 准则：惰性初始化，确保绑定在当前运行的 Event Loop
            self._client = httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=100))
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def chat(self, request: Request):
        try:
            body = await request.json()
            model_name = body.get("model")
            
            # 1. 准入审计
            tier = await self.scout.get_model_tier(model_name)
            
            # 2. 拦截控制
            if tier == "TIER_3_BASIC" and "tools" in body:
                raise HTTPException(status_code=422, detail=f"Model {model_name} cannot handle tools.")

            # 3. 流水线优化
            if "messages" in body:
                for msg in body["messages"]:
                    if "content" in msg and msg.get("content"):
                        msg["content"] = self.pipeline.compressor.compress(msg["content"])
                # 注入安全增强
                from src.models import StandardRequest, Message # 临时转化进行 Enforce
                temp_req = StandardRequest(model=model_name, messages=[Message(**m) for r in [body] for m in r['messages']])
                self.pipeline.enforcer.apply(temp_req, tier)
                # 写回 body
                for i, msg in enumerate(temp_req.messages):
                    body["messages"][i]["content"] = msg.content

            # 4. 异步转发与流式处理
            if body.get("stream", False):
                async def stream_generator():
                    async with self.client.stream("POST", f"{self.base_url}/api/chat", json=body) as response:
                        # 2.4 准则：迭代前检查错误
                        if response.is_error:
                            yield json.dumps({"error": "Backend Error", "status": response.status_code}).encode()
                            return
                        async for chunk in response.aiter_bytes():
                            yield chunk
                return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
            else:
                resp = await self.client.post(f"{self.base_url}/api/chat", json=body)
                return resp.json()

        except Exception as e:
            if isinstance(e, HTTPException): raise e
            raise HTTPException(status_code=502, detail=str(e))

    async def list_models(self):
        resp = await self.client.get(f"{self.base_url}/api/tags")
        return resp.json()
