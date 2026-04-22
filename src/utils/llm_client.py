import os
import httpx
import json
import logging
import re
import asyncio
from typing import List, Dict, Any, Optional, Union
from src.models import Message, StandardRequest, StandardResponse

logger = logging.getLogger("GATEWAY.UTILS.LLM_CLIENT")

class LLMClient:
    """
    Unified LLM Client for ClawBrain Cognitive Plane.
    Supports Ollama and OpenAI-compatible providers.
    """
    def __init__(self, url: str = None, model: str = None, provider: str = "ollama", api_key: str = None):
        self.url = url
        self.model = model
        self.provider = provider or "ollama"
        self.api_key = api_key or os.getenv("CLAWBRAIN_DISTILL_API_KEY", "")

    async def generate(self, prompt: str, system_prompt: str = "You are a professional memory assistant.", 
                       json_mode: bool = False, timeout: float = 60.0) -> StandardResponse:
        """
        Unified generation method.
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                if self.provider == "ollama":
                    return await self._generate_ollama(client, headers, prompt, system_prompt, json_mode)
                else:
                    return await self._generate_openai(client, headers, prompt, system_prompt, json_mode)
            except Exception as e:
                logger.error(f"[LLM_CLIENT] Request failed: {e}")
                raise

    async def _generate_ollama(self, client, headers, prompt, system, json_mode) -> StandardResponse:
        url = f"{self.url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False
        }
        if json_mode:
            payload["format"] = "json"

        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        
        return StandardResponse(
            id=data.get("created_at", "ollama"),
            model=self.model,
            created=int(asyncio.get_event_loop().time()),
            message=Message(role="assistant", content=data.get("response", "")),
            done=True
        )

    async def _generate_openai(self, client, headers, prompt, system, json_mode) -> StandardResponse:
        url = f"{self.url.rstrip('/')}/chat/completions"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        
        return StandardResponse(
            id=data.get("id", "openai"),
            model=self.model,
            created=data.get("created", 0),
            message=Message(
                role="assistant", 
                content=choice["message"].get("content", ""),
                tool_calls=choice["message"].get("tool_calls")
            ),
            done=True
        )

    @staticmethod
    def parse_json(text: str) -> Any:
        """Helper to extract and parse JSON from LLM response strings."""
        try:
            # Strip markdown code blocks
            clean = re.sub(r'```json\s*|\s*```', '', text).strip()
            return json.loads(clean)
        except Exception as e:
            logger.warning(f"[LLM_CLIENT] JSON parse failed: {e} | Text: {text[:100]}...")
            raise
