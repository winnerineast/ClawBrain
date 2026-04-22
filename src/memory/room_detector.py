# Generated from design/memory_rooms.md v1.0
import os
import logging
from typing import List, Dict, Any, Optional
from src.utils.llm_client import LLMClient

logger = logging.getLogger("GATEWAY.MEMORY.ROOMS")

class RoomDetector:
    """
    Topic-Aware Room Segmentation Engine.
    Detects conversation context shifts and organizes traces into semantic Rooms.
    """
    
    SYSTEM_PROMPT = (
        "You are a highly precise conversation topic classifier. Your ONLY job is to assign the CURRENT TURN to a specific topic-based 'Room'.\n"
        "Rules:\n"
        "1. If the current turn continues an existing topic from the recent history, output the EXACT NAME of that room.\n"
        "2. If the current turn starts a different topic, you MUST output a NEW, concise room name (max 2 words).\n"
        "3. NEVER output 'general' unless the input is just a greeting.\n"
        "Output ONLY the room name string. No preamble."
    )

    def __init__(self, url: str = None, model: str = None, provider: str = "ollama", api_key: str = ""):
        self.llm = LLMClient(
            url=url or os.getenv("CLAWBRAIN_DISTILL_URL", "http://127.0.0.1:11434"),
            model=model or os.getenv("CLAWBRAIN_DISTILL_MODEL", "gemma4:e4b"),
            provider=provider or os.getenv("CLAWBRAIN_DISTILL_PROVIDER", "ollama"),
            api_key=api_key
        )

    async def detect_room(self, history: List[str], current_turn: str, existing_rooms: List[str]) -> str:
        """
        Predict the room name for the current turn given history and existing rooms.
        """
        prompt = f"Existing Rooms: {', '.join(existing_rooms) if existing_rooms else 'None'}\n\n"
        prompt += "Recent History:\n"
        for h in history[-3:]:
            prompt += f"- {h}\n"
        prompt += f"\nCurrent Turn: {current_turn}\n\nDetected Room Name:"

        try:
            resp = await self.llm.generate(prompt, system_prompt=self.SYSTEM_PROMPT, timeout=30.0)
            result = resp.message.content.strip().lower()
            
            # Sanitize: max 2 words, lowercase
            sanitized = "-".join(result.split()[:2]).replace("'", "").replace('"', "")
            return sanitized or "general"
        except Exception as e:
            logger.warning(f"[ROOM_DETECTOR] Failed to detect room: {e}. Falling back to 'general'.")
            return "general"
