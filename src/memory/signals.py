# Generated from design/memory.md v1.8
import hashlib
import json
import re
from typing import Dict, Any, Set, List

class SignalDecomposer:
    """
    负责将原始 Payload 拆解为背景、环境和核心信号。
    v1.9: Entity-Aware Signaling implemented.
    """
    
    @staticmethod
    def get_schema_fingerprint(payload: Dict[str, Any]) -> str:
        """
        Extract a unique structural fingerprint from the request.
        Rule 2.2: Exclude message content to fingerprint the protocol structure.
        """
        # Create a content-free copy of the payload
        try:
            p_copy = json.loads(json.dumps(payload))
        except (TypeError, ValueError):
            p_copy = payload.copy()
        
        if "messages" in p_copy:
            for m in p_copy["messages"]:
                if isinstance(m, dict):
                    m["content"] = "" # Strip content
                
        if "prompt" in p_copy:
            p_copy["prompt"] = ""
            
        # Ensure dict keys are ordered for hash stability
        try:
            stable_json = json.dumps(p_copy, sort_keys=True)
        except (TypeError, ValueError):
            stable_json = str(sorted(p_copy.items()))
            
        return hashlib.sha256(stable_json.encode()).hexdigest()

    @staticmethod
    def extract_core_intent(payload: Dict[str, Any]) -> str:
        """
        Extract the core stimulus text from the payload.
        Rule 2.2: Precisely strip the last user message content.
        """
        messages = payload.get("messages", [])
        if not isinstance(messages, list) or not messages:
            # Fallback for stimulus wrapper
            messages = payload.get("stimulus", {}).get("messages", [])
            if not isinstance(messages, list) or not messages:
                return str(payload.get("prompt", ""))
            
        # Search backwards for the first user message
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                return m.get("content", "")
                
        return str(payload.get("prompt", ""))

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
        stop_entities = {"The", "What", "How", "When", "Where", "Which", "Who", "Whom", "This", "That", "These", "Those", "There", "If", "While", "As", "But", "And", "Or"}
        proper_nouns_raw = re.findall(r'\b[A-Z][a-z]+(?: [A-Z][a-z]+)*\b', content)
        proper_nouns = [n for n in proper_nouns_raw if n not in stop_entities]
        
        # 3. Numeric specific facts: Ports, Versions (v1.2.3, 5432)
        versions_ports = re.findall(r'\b(?:v?\d+\.\d+\.?\d*|\d{4,5})\b', content)
        
        return set(tech_ids + proper_nouns + versions_ports)

    # Aliases for backward compatibility
    def extract_fingerprint(self, payload: Dict[str, Any]) -> str:
        return self.get_schema_fingerprint(payload)

    def extract_stimulus_content(self, payload: Dict[str, Any]) -> str:
        return self.extract_core_intent(payload)
