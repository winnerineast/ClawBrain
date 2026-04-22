import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
from src.utils.llm_client import LLMClient

logger = logging.getLogger("GATEWAY.MEMORY.ENTITIES")

class EntityExtractor:
    """
    ClawBrain Entity Awareness & Attribute Tracking Engine.
    Implementation of design/memory_entities.md v1.0.
    """
    def __init__(self, url: str = None, model: str = None, provider: str = "ollama"):
        self.llm = LLMClient(
            url=os.getenv("CLAWBRAIN_DISTILL_URL", url or "http://127.0.0.1:11434"),
            model=os.getenv("CLAWBRAIN_DISTILL_MODEL", model or "gemma4:e4b"),
            provider=os.getenv("CLAWBRAIN_DISTILL_PROVIDER", provider or "ollama")
        )

    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract specific entity attributes from the dialogue.
        Returns a list of dicts: [{"entity": "...", "key": "...", "value": "..."}]
        """
        system = (
            "Extract specific entity attributes from the provided dialogue.\n"
            "Return a JSON list of objects: [{\"entity\": \"...\", \"key\": \"...\", \"value\": \"...\"}].\n"
            "STRICT GUIDELINES:\n"
            "1. ONLY extract hard facts (versions, IPs, roles, project names, technology choices).\n"
            "2. IGNORE general conversation or greetings.\n"
            "3. If no entities or attributes are found, return []."
        )
        
        prompt = f"--- DIALOGUE ---\n{text}\n\nExtract JSON entities:"
        
        try:
            resp = await self.llm.generate(prompt, system_prompt=system, json_mode=True, timeout=30.0)
            data = self.llm.parse_json(resp.message.content)
            
            if isinstance(data, list): return data
            if isinstance(data, dict) and "entities" in data: return data["entities"]
            if isinstance(data, dict): return [data]
        except Exception as e:
            logger.warning(f"[ENTITIES] Extraction failed: {e}")
        return []
