# Generated from design/gateway.md v1.17
import httpx
import json
import logging
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
            
            # 1. 执行准入契约判定
            tier = await self.scout.get_model_tier(model_name)
            
            # 4. 审计日志输出 (按规格书定义)
            print(f"[MODEL_QUAL] Model: {model_name} | Tier: {tier.value} | Action: {'BLOCK' if tier == ModelTier.TIER_3 and 'tools' in body else 'PASS'}")

            # 2. 强制拦截 KPI
            if tier == ModelTier.TIER_3 and "tools" in body:
                raise HTTPException(status_code=422, detail=f"KPI Violation: Model {model_name} (TIER_3) is not qualified for Tool Calling.")

            # 3. 提纯优化 (Pipeline)
            if "messages" in body:
                for msg in body["messages"]:
                    if "content" in msg and msg["content"]:
                        msg["content"] = self.pipeline.compressor.compress(msg["content"])
                
                # TIER_2 指令增强
                if tier == ModelTier.TIER_2:
                    from src.models import StandardRequest, Message
                    temp_req = StandardRequest(model=model_name, messages=[Message(**m) for m in body["messages"]])
                    self.pipeline.enforcer.apply(temp_req, tier)
                    for i, m in enumerate(temp_req.messages): body["messages"][i]["content"] = m.content

            # 4. 转发
            if body.get("stream", False):
                async def stream_generator():
                    async with self.client.stream("POST", f"{self.base_url}/api/chat", json=body) as resp:
                        if resp.is_error:
                            yield json.dumps({"error": "Backend KPI Failure"}).encode()
                            return
                        async for chunk in resp.aiter_bytes():
                            yield chunk
                return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
            else:
                resp = await self.client.post(f"{self.base_url}/api/chat", json=body)
                return resp.json()

        except Exception as e:
            if isinstance(e, HTTPException): raise e
            # 异常降级 502 并记录日志
            logging.error(f"Adapter error: {e}")
            raise HTTPException(status_code=502, detail=str(e))

    async def list_models(self):
        resp = await self.client.get(f"{self.base_url}/api/tags")
        return resp.json()
