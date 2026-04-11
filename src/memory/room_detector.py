# Generated from design/memory_rooms.md v1.0
import httpx
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("GATEWAY.MEMORY.ROOMS")

class RoomDetector:
    """
    Topic-Aware Room Segmentation Engine.
    Detects conversation context shifts and organizes traces into semantic Rooms.
    """
    
    SYSTEM_PROMPT = """
    You are a highly precise conversation topic classifier. Your ONLY job is to assign the CURRENT TURN to a specific topic-based "Room".
    
    Rules:
    1. If the current turn continues an existing topic from the recent history, output the EXACT NAME of that room.
    2. If the current turn starts a different topic, you MUST output a NEW, concise room name (max 2 words, e.g., 'database', 'css', 'python-api').
    3. NEVER output 'general' unless the input is literally just a greeting like 'hello' with no subject.
    
    Response Format:
    Output ONLY the room name string. No preamble, no punctuation, no quotes.
    """

    def __init__(self, url: str, model: str, provider: str = "ollama", api_key: str = "", client: httpx.AsyncClient = None):
        self.url = url
        self.model = model
        self.provider = provider
        self.api_key = api_key
        self.http_client = client

    async def detect_room(self, history: List[str], current_turn: str, existing_rooms: List[str]) -> str:
        """
        Predict the room name for the current turn given history and existing rooms.
        """
        prompt = f"Existing Rooms in this session: {', '.join(existing_rooms) if existing_rooms else 'None'}\n\n"
        prompt += "Recent History (last 3 turns):\n"
        for h in history[-3:]:
            prompt += f"- {h}\n"
        prompt += f"\nCurrent Turn: {current_turn}\n\n"
        prompt += "Detected Room Name:"

        try:
            # Phase 34: Use Cognitive Plane client
            if self.http_client:
                return await self._dispatch_detect(self.http_client, prompt)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    return await self._dispatch_detect(client, prompt)
                
        except Exception as e:
            logger.warning(f"[ROOM_DETECTOR] Failed to detect room: {e}. Falling back to 'general'.")
            return "general"

    async def _dispatch_detect(self, client: httpx.AsyncClient, prompt: str) -> str:
        if self.provider == "ollama":
            resp = await client.post(
                f"{self.url}/api/generate",
                json={"model": self.model, "prompt": self.SYSTEM_PROMPT + "\n\n" + prompt, "stream": False}
            )
            resp.raise_for_status()
            result = resp.json().get("response", "general").strip().lower()
        else:
            # OpenAI compatible
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            resp = await client.post(
                f"{self.url}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.0
                }
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip().lower()
        
        # Sanitize: max 3 words, lowercase
        sanitized = "-".join(result.split()[:3]).replace("'", "").replace('"', "")
        return sanitized or "general"
