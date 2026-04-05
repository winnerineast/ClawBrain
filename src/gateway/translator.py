# Generated from design/gateway.md v1.38
import json
from typing import Dict, Any, AsyncGenerator, List
from src.models import StandardRequest

class DialectTranslator:
    """
    万能方言翻译器。
    负责将 StandardRequest 转换为各 Provider 的原生格式。
    """
    
    @staticmethod
    def to_ollama(request: StandardRequest) -> Dict[str, Any]:
        return request.model_dump(exclude_none=True)

    @staticmethod
    def to_openai(request: StandardRequest) -> Dict[str, Any]:
        """
        翻译为标准 OpenAI 格式。
        2.1 准则修正：只剥离第一个前缀（网关标识），保留模型内部路径。
        解决 LM Studio 400 错误。
        """
        payload = request.model_dump(exclude_none=True)
        model_name = payload.get("model", "")
        if "/" in model_name:
            # lmstudio/nvidia/model -> nvidia/model
            payload["model"] = model_name.split("/", 1)[1]
            
        payload.pop("options", None)
        return payload

    @staticmethod
    def to_anthropic(request: StandardRequest) -> Dict[str, Any]:
        """翻译为 Anthropic (Claude) 格式"""
        raw = request.model_dump(exclude_none=True)
        messages = raw.get("messages", [])
        
        system_parts = []
        normalized = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                if normalized and normalized[-1]["role"] == msg["role"]:
                    normalized[-1]["content"] += "\n" + msg.get("content", "")
                else:
                    normalized.append({"role": msg["role"], "content": msg.get("content", "")})
        
        # 2.1 准则修正：只剥离第一个前缀
        model_name = raw.get("model", "")
        target_model = model_name.split("/", 1)[1] if "/" in model_name else model_name

        anthropic_body = {
            "model": target_model,
            "max_tokens": raw.get("max_tokens") or 4096,
            "messages": normalized,
            "stream": raw.get("stream", False)
        }
        if system_parts:
            anthropic_body["system"] = "\n".join(system_parts)
        return anthropic_body

    @staticmethod
    def to_google(request: StandardRequest) -> Dict[str, Any]:
        """翻译为 Google Gemini 格式"""
        raw = request.model_dump(exclude_none=True)
        messages = raw.get("messages", [])
        
        contents = []
        system_instruction = ""
        
        for msg in messages:
            if msg.get("role") == "system":
                system_instruction += msg.get("content", "") + "\n"
            else:
                role = "model" if msg.get("role") == "assistant" else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })
        
        google_body = {
            "contents": contents,
            "generationConfig": {
                "temperature": raw.get("temperature", 0.7),
                "maxOutputTokens": raw.get("max_tokens", 4096)
            }
        }
        if system_instruction:
            google_body["system_instruction"] = {"parts": [{"text": system_instruction.strip()}]}
            
        return google_body

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
