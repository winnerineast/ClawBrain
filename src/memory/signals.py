# Generated from design/memory.md v1.8
import hashlib
import json
import re
from typing import Dict, Any, Set

class SignalDecomposer:
    """
    负责将原始 Payload 拆解为背景、环境和核心信号。
    v1.9: Entity-Aware Signaling implemented.
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
            # P47: Check stimulus wrapper
            messages = payload.get("stimulus", {}).get("messages", [])
            if not messages: return ""
        
        # 从后往前找第一条 user 消息
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    @staticmethod
    def extract_entities(content: str) -> Set[str]:
        """
        v1.9: Extract hard anchors (Technical IDs, IPs, Proper Nouns, Versions).
        Robust against conversational noise and common start-of-sentence stop words.
        """
        if not content: return set()
        
        # 1. Technical Identifiers: ALL_CAPS_WITH_NUMS, UUIDs, FQDNs, IPs
        tech_ids = re.findall(r'\b(?:[A-Z0-9_\-\.]{4,}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\b', content)
        
        # 2. Proper Nouns: Capitalized words (excluding common stop words at start of sentences)
        # Capture multi-word proper nouns: "MongoDB Atlas", "Amazon Web Services"
        stop_entities = {"The", "What", "How", "When", "Where", "Which", "Who", "Whom", "This", "That", "These", "Those", "There", "If", "While", "As", "But", "And", "Or"}
        proper_nouns_raw = re.findall(r'\b[A-Z][a-z]+(?: [A-Z][a-z]+)*\b', content)
        proper_nouns = [n for n in proper_nouns_raw if n not in stop_entities]
        
        # 3. Numeric specific facts: Ports, Versions (v1.2.3, 5432)
        versions_ports = re.findall(r'\b(?:v?\d+\.\d+\.?\d*|\d{4,5})\b', content)
        
        return set(tech_ids + proper_nouns + versions_ports)
