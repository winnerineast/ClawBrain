# Generated from design/memory_rooms.md v1.2
import httpx
import logging
from typing import List, Dict, Any, Optional
from src.utils.llm_client import LLMFactory, ChatClient

logger = logging.getLogger("GATEWAY.MEMORY.ROOMS")

class RoomDetector:
    """
    Topic-Aware Room Segmentation Engine.
    v1.2: Standardized via ChatClient and LLMFactory.
    """
    
    SYSTEM_PROMPT = """
    You are a highly precise conversation topic classifier. Your ONLY job is to assign the CURRENT TURN to a specific topic-based "Room".
    Respond ONLY with the room name string. No preamble, no punctuation, no quotes.
    """

    def __init__(self, url: str, model: str, provider: str = "ollama", api_key: str = ""):
        self.url = url
        self.model = model
        self.provider = provider
        self.api_key = api_key
        
        # v1.2: Standardized ChatClient
        self.llm = LLMFactory.get_chat_client(self.provider, self.url, self.model, self.api_key)

    async def detect_room(self, history: List[str], current_turn: str, existing_rooms: List[str]) -> str:
        prompt = f"Existing Rooms: {', '.join(existing_rooms)}\n\nRecent History:\n" + "\n".join(history[-3:])
        prompt += f"\nCurrent Turn: {current_turn}\n\nDetected Room Name:"

        try:
            result = await self.llm.generate(prompt=prompt, system=self.SYSTEM_PROMPT)
            if "[Error]" in result: return "general"
            sanitized = "-".join(result.strip().lower().split()[:3]).replace("'", "").replace('"', "")
            return sanitized or "general"
        except:
            return "general"
