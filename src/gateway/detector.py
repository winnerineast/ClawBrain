# Generated from design/gateway.md v1.33
from typing import Dict, Any, Tuple
from src.models import StandardRequest

class ProtocolDetector:
    """
    负责将不同客户端协议标准化。
    2.3 准则修正：深度提取 tools, options, stream 等元数据。
    """
    @staticmethod
    def detect_and_standardize(payload: Dict[str, Any]) -> Tuple[str, StandardRequest]:
        # 1. 探测协议
        source_protocol = "ollama" if "options" in payload else "openai"
        
        # 2. 深度元数据对齐
        # 尝试从顶层、options 或 extra_body 中提取 tools
        tools = payload.get("tools")
        if not tools and "options" in payload:
            # 某些 Ollama 客户端可能将 tools 放入 options
            tools = payload["options"].get("tools")
            
        stream = payload.get("stream", False)
        
        # 3. 构造标准请求
        try:
            req = StandardRequest(**payload)
            # 强制覆盖以确保元数据完整
            if tools: req.tools = tools
            req.stream = stream
        except Exception as e:
            raise ValueError(f"Standardization failed: {e}")
            
        return source_protocol, req
