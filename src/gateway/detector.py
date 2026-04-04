# Generated from design/gateway.md v1.22
from typing import Dict, Any
from src.models import StandardRequest, Message, Tool

class ProtocolDetector:
    """
    负责将来自不同客户端协议的 HTTP Payload 转化为 ClawBrain 的 StandardInteractionRequest。
    """
    @staticmethod
    def detect_and_standardize(payload: Dict[str, Any]) -> tuple[str, StandardRequest]:
        # 探测：如果带有 'messages' 和 'model'，且具备 OpenAI 的特定结构，或者是 Ollama
        # 为简化，当前内部的 StandardRequest 设计已经兼容两者。
        
        # 判断来源协议 (用于之后决定反向翻译流的格式)
        # OpenAI 通常包含 'temperature' 字段且没有 'options' 的字典结构，但这不可靠。
        # 这里用一种简单启发式：如果在顶层存在 options，大概率是 Ollama 原生。
        source_protocol = "ollama" if "options" in payload else "openai"
        
        # Standardize (统一成 Pydantic 模型，剔除杂质)
        try:
            req = StandardRequest(**payload)
        except Exception as e:
            raise ValueError(f"Payload standardization failed: {e}")
            
        return source_protocol, req
