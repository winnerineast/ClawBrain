# Generated from design/memory_router.md v1.12
import json
import hashlib
from typing import Dict, Any, List

class SignalDecomposer:
    """
    Cognitive Signal Decomposer.
    Responsible for breaking down raw payloads into background, environment, and core signals.
    Implemented based on design/memory.md v1.8.
    """
    
    def extract_fingerprint(self, payload: Dict[str, Any]) -> str:
        """
        Extract a unique structural fingerprint from the request.
        Rule 2.2: Exclude message content to fingerprint the protocol structure.
        """
        # Create a content-free copy of the payload
        p_copy = json.loads(json.dumps(payload))
        
        if "messages" in p_copy:
            for m in p_copy["messages"]:
                m["content"] = "" # Strip content
                
        if "prompt" in p_copy:
            p_copy["prompt"] = ""
            
        # Ensure dict keys are ordered for hash stability
        stable_json = json.dumps(p_copy, sort_keys=True)
        return hashlib.sha256(stable_json.encode()).hexdigest()

    def extract_stimulus_content(self, payload: Dict[str, Any]) -> str:
        """
        Extract the core stimulus text from the payload.
        Rule 2.2: Precisely strip the last user message content.
        """
        messages = payload.get("messages", [])
        # Search backwards for the first user message
        for m in reversed(messages):
            if m.get("role") == "user":
                return m.get("content", "")
                
        return payload.get("prompt", "")
