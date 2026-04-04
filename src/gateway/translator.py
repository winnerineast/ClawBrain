# Generated from design/gateway_cloud.md v1.1
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
        if "/" in payload.get("model", ""):
            payload["model"] = payload["model"].split("/", 1)[1]
        payload.pop("options", None)
        return payload

    @staticmethod
    def to_anthropic(request: StandardRequest) -> Dict[str, Any]:
        """
        2.1 准则：翻译为 Anthropic (Claude) 规格。
        处理：System 提取、max_tokens 补全、角色交替修复。
        """
        raw_payload = request.model_dump(exclude_none=True)
        messages = raw_payload.get("messages", [])
        
        system_parts = []
        normalized_messages = []
        
        # 1. 提取 System
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                # 2. 角色交替规范：合并连续相同角色
                if normalized_messages and normalized_messages[-1]["role"] == msg["role"]:
                    normalized_messages[-1]["content"] += "\n" + msg.get("content", "")
                else:
                    normalized_messages.append({
                        "role": msg["role"],
                        "content": msg.get("content", "")
                    })
        
        # 3. 构造规格 Body
        anthropic_payload = {
            "model": raw_payload.get("model", "").split("/")[-1],
            "max_tokens": raw_payload.get("max_tokens") or 4096, # 2.1 必填项补全
            "messages": normalized_messages,
            "stream": raw_payload.get("stream", False)
        }
        
        if system_parts:
            anthropic_payload["system"] = "\n".join(system_parts)
            
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
