# Generated from design/gateway_cloud.md v1.0
import json
from typing import Dict, Any, AsyncGenerator, List
from src.models import StandardRequest

class DialectTranslator:
    """
    负责将内部 StandardRequest 翻译为目标提供商的专属方言。
    """
    @staticmethod
    def to_ollama(request: StandardRequest) -> Dict[str, Any]:
        return request.model_dump(exclude_none=True)

    @staticmethod
    def to_openai(request: StandardRequest) -> Dict[str, Any]:
        payload = request.model_dump(exclude_none=True)
        # 移除模型前缀
        if "/" in payload.get("model", ""):
            payload["model"] = payload["model"].split("/", 1)[1]
        payload.pop("options", None)
        return payload

    @staticmethod
    def to_anthropic(request: StandardRequest) -> Dict[str, Any]:
        """
        2.1 准则：翻译为 Anthropic (Claude) 专属格式。
        核心逻辑：剥离 system message 到顶层字段。
        """
        raw_payload = request.model_dump(exclude_none=True)
        messages = raw_payload.get("messages", [])
        
        system_content = ""
        user_assistant_messages = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_content += msg.get("content", "") + "\n"
            else:
                user_assistant_messages.append(msg)
        
        anthropic_payload = {
            "model": raw_payload.get("model", "").split("/")[-1],
            "max_tokens": raw_payload.get("max_tokens", 4096),
            "system": system_content.strip(),
            "messages": user_assistant_messages,
            "stream": raw_payload.get("stream", False)
        }
        return anthropic_payload

    @staticmethod
    async def reverse_stream_ollama_to_openai(response_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        async for chunk in response_stream:
            if not chunk: continue
            try:
                data = json.loads(chunk)
                openai_chunk = {
                    "id": "chatcmpl-claw", "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"content": data.get("message", {}).get("content", "")}}]
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n"
                if data.get("done"): yield "data: [DONE]\n\n"
            except: pass
