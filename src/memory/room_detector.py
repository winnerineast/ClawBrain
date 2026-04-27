# Generated from design/memory_rooms.md v1.1
import httpx
import logging
from typing import List, Dict, Any, Optional
from src.utils.llm_client import LLMFactory, LLMClient

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
        
        # Decoupled LLM Client
        self.llm = LLMFactory.get_client(self.provider, self.url, self.model, self.api_key, timeout=60.0)

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
            result = await self.llm.generate(prompt=prompt, system=self.SYSTEM_PROMPT)
            
            if "[Error]" in result:
                raise Exception(result)
                
            # Sanitize: max 3 words, lowercase
            sanitized = "-".join(result.strip().lower().split()[:3]).replace("'", "").replace('"', "")
            return sanitized or "general"
                
        except Exception as e:
            logger.warning(f"[ROOM_DETECTOR] Failed to detect room: {e}. Falling back to 'general'.")
            return "general"
