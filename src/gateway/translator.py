# Generated from design/gateway.md v1.22
import json
from typing import Dict, Any, AsyncGenerator
from src.models import StandardRequest

class DialectTranslator:
    """
    将内部 StandardRequest 翻译为具体 Provider 认可的专属方言。
    并且负责反向翻译流式响应。
    """
    
    @staticmethod
    def to_ollama(request: StandardRequest) -> Dict[str, Any]:
        """翻译为 Ollama (v1) API 格式"""
        payload = request.model_dump(exclude_none=True)
        # Ollama 特有字段在模型中已经基本对应，不需要太多转换
        return payload

    @staticmethod
    def to_openai(request: StandardRequest) -> Dict[str, Any]:
        """翻译为 OpenAI Chat Completions 格式"""
        # OpenAI 需要去除模型名前的 provider 标识
        payload = request.model_dump(exclude_none=True)
        raw_model = payload.get("model", "")
        if "/" in raw_model:
            payload["model"] = raw_model.split("/", 1)[1]
            
        # 移除 ollama 特有的 options 字段
        payload.pop("options", None)
        return payload

    @staticmethod
    async def reverse_stream_ollama_to_openai(response_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """
        接收 Ollama 的 NDJSON 流，实时转换为 OpenAI 的 SSE 流。
        """
        async for chunk in response_stream:
            if not chunk: continue
            try:
                # 解析 Ollama NDJSON: {"model":"...", "message":{"content":"hi"}, "done":false}
                data = json.loads(chunk)
                if "error" in data:
                    yield f"data: {json.dumps(data)}\n\n"
                    continue
                    
                msg_content = data.get("message", {}).get("content", "")
                is_done = data.get("done", False)
                
                # 包装为 OpenAI SSE chunk
                openai_chunk = {
                    "id": "chatcmpl-clawbrain",
                    "object": "chat.completion.chunk",
                    "model": data.get("model", "unknown"),
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": msg_content},
                            "finish_reason": "stop" if is_done else None
                        }
                    ]
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n"
                
                if is_done:
                    yield "data: [DONE]\n\n"
                    
            except Exception as e:
                # 流式解析错误容错
                pass
