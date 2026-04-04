# Generated from design/gateway.md v1.20
from fastapi import Request, HTTPException

class OpenAIAdapter:
    """
    OpenAI 适配器。
    Phase 4 预留，目前返回 501。
    """
    async def chat(self, request: Request):
        raise HTTPException(status_code=501, detail="Official OpenAI API support is planned for future phases.")
