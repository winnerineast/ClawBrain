# Generated from design/memory.md v1.8
import hashlib
import json
from typing import Dict, Any

class SignalDecomposer:
    """
    负责将原始 Payload 拆解为背景、环境和核心信号。
    基于 design/memory.md v1.8 实现。
    """
    
    @staticmethod
    def get_schema_fingerprint(payload: Dict[str, Any]) -> str:
        # 2.2 准则：排除消息内容，对协议结构进行指纹识别
        struct_only = {k: v for k, v in payload.items() if k != "messages"}
        # 确保字典 key 有序，保证 Hash 稳定性
        encoded = json.dumps(struct_only, sort_keys=True).encode()
        return hashlib.md5(encoded).hexdigest()

    @staticmethod
    def extract_core_intent(payload: Dict[str, Any]) -> str:
        # 2.2 准则：精准剥离最后一条 user 消息内容
        messages = payload.get("messages", [])
        if not messages:
            return ""
        
        # 从后往前找第一条 user 消息
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""
