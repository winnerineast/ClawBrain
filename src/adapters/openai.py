# Generated from design/gateway.md v1.11
from fastapi import Request, HTTPException

class OpenAIAdapter:
    async def chat(self, request: Request):
        # Phase 4 仅预留入口
        raise HTTPException(status_code=501, detail="OpenAI Adapter not yet implemented in Phase 4.")
