# Generated from design/memory.md v1.7
import hashlib
import json

class SignalDecomposer:
    """负责将原始 Payload 拆解为背景、环境和核心信号"""
    
    @staticmethod
    def get_schema_fingerprint(payload: Dict[str, Any]) -> str:
        # 提取 OpenClaw 常用的工具定义或系统前缀部分进行 Hash
        # 这里简化处理：对整个请求结构（不含 messages 内容）进行指纹识别
        struct = {k: v for k, v in payload.items() if k != "messages"}
        return hashlib.md5(json.dumps(struct, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def extract_core_intent(payload: Dict[str, Any]) -> str:
        # 逻辑：从 messages 数组的最后一条 user 消息中提取意图
        messages = payload.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""
