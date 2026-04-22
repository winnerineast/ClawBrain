import os
import httpx
import json
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger("GATEWAY.MEMORY.ENTITIES")

class EntityExtractor:
    """
    ClawBrain Entity Awareness & Attribute Tracking Engine.
    Implementation of design/memory_entities.md v1.0.
    """
    def __init__(self, url: str = None, model: str = None, provider: str = "ollama"):
        self.url = os.getenv("CLAWBRAIN_DISTILL_URL", url or "http://127.0.0.1:11434")
        self.model = os.getenv("CLAWBRAIN_DISTILL_MODEL", model or "gemma4:e4b")
        self.provider = os.getenv("CLAWBRAIN_DISTILL_PROVIDER", provider or "ollama")
        self.api_key = os.getenv("CLAWBRAIN_DISTILL_API_KEY", "")

    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract specific entity attributes from the dialogue.
        Returns a list of dicts: [{"entity": "...", "key": "...", "value": "..."}]
        """
        instruction = (
            "Extract specific entity attributes from the provided dialogue.\n"
            "Return a JSON list of objects: [{\"entity\": \"...\", \"key\": \"...\", \"value\": \"...\"}].\n"
            "STRICT GUIDELINES:\n"
            "1. ONLY extract hard facts (versions, IPs, roles, project names, technology choices).\n"
            "2. IGNORE general conversation or greetings.\n"
            "3. If no entities or attributes are found, return an empty list [].\n"
            "4. DO NOT provide any explanation, only the raw JSON list."
        )
        
        prompt = f"{instruction}\n\n--- DIALOGUE ---\n{text}\n\nJSON Output:"
        
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                if self.provider == "ollama":
                    url = f"{self.url.rstrip('/')}/api/generate"
                    resp = await client.post(url, headers=headers, json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json"
                    })
                    if resp.status_code == 200:
                        raw_response = resp.json().get("response", "[]")
                        return self._parse_json_safely(raw_response)
                else:
                    # OpenAI compatible
                    url = f"{self.url.rstrip('/')}/chat/completions"
                    resp = await client.post(url, headers=headers, json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"}
                    })
                    if resp.status_code == 200:
                        raw_content = resp.json()["choices"][0]["message"]["content"]
                        return self._parse_json_safely(raw_content)
        except Exception as e:
            logger.warning(f"[ENTITIES] Extraction failed: {e}")
        return []

    def _parse_json_safely(self, text: str) -> List[Dict[str, Any]]:
        try:
            # Clean text from potential markdown wrappers
            clean_text = re.sub(r'```json\s*|\s*```', '', text).strip()
            data = json.loads(clean_text)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "entities" in data:
                return data["entities"]
            return []
        except:
            return []
