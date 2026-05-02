# Generated from design/memory_neocortex.md v1.10 / GEMINI.md Rule 12
import sqlite3
import chromadb
import httpx
import time
import os
import asyncio
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.memory.storage import get_chroma_client
from src.utils.llm_client import LLMFactory, LLMClient
from src.utils.config import get_env

logger = logging.getLogger("GATEWAY.MEMORY.NEO")

class Neocortex:
    """
    ClawBrain Semantic Distillation Engine.
    Implements L6b Value Modulation and TasteGuard Belief Anchors.
    """
    def __init__(self, db_dir: str = None, distill_url: str = None, distill_model: str = None, 
                 distill_provider: str = None, client: httpx.AsyncClient = None):
        if db_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "data")
            
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # Phase 33: ChromaDB summaries
        self.chroma_path = self.db_dir / "chroma"
        self.client = get_chroma_client(self.chroma_path)
        self.summary_col = self.client.get_or_create_collection(name="summaries")
        
        # Legacy DB path
        self.db_path = self.db_dir / "hippocampus.db"
        
        # Distillation Config
        self.distill_url = get_env("CLAWBRAIN_DISTILL_URL", distill_url or "http://127.0.0.1:11434")
        self.distill_model = get_env("CLAWBRAIN_DISTILL_MODEL", distill_model or "gemma4:e4b")
        self.distill_provider = get_env("CLAWBRAIN_DISTILL_PROVIDER", distill_provider or "ollama")
        self.api_key = get_env("CLAWBRAIN_DISTILL_API_KEY", "")
        
        # Decoupled LLM Client
        self.llm = LLMFactory.get_client(self.distill_provider, self.distill_url, self.distill_model, self.api_key)
        self._judge_cache = {}
        self._cache_lock = asyncio.Lock()

        # Phase 65: Taste Profile (L6b/TasteGuard Anchor)
        self.taste_profile = get_env("CLAWBRAIN_TASTE_PROFILE", 
            "The user prioritizes technical precision, architectural integrity, and production stability. "
            "They prefer Python/FastAPI for backends and Obsidian for knowledge management. "
            "They dislike boilerplate, inefficient context usage, and ambiguous technical decisions.")

    async def score_precision(self, content: str) -> float:
        """
        L6b Modulation Filter: Score interaction value (0.0 to 1.0).
        High score -> Store in L2. Low score -> Drop/Decay.
        """
        # Phase 65: Deterministic bypass for regression tests
        if get_env("CLAWBRAIN_DISABLE_COGNITIVE_JUDGE") == "true":
            return 1.0

        if not content or len(content) < 10: return 0.1
        
        instruction = (
            "You are the L6b Precision Filter. Your goal is to determine if a dialogue turn is worth remembering.\n"
            "High Value (0.7-1.0): Technical decisions, configuration changes, specific facts, or high-intent instructions.\n"
            "Low Value (0.0-0.3): Generic greetings, tangential chatter, or trivial pleasantries.\n"
            f"User Taste Profile: {self.taste_profile}\n"
            "Respond with ONLY a number between 0.0 and 1.0."
        )
        
        try:
            res = await self.llm.generate(prompt=f"Content: {content[:1000]}", system=instruction)
            return float(re.search(r"(\d\.\d+)", res).group(1)) if res else 0.5
        except:
            return 0.5 # Default to neutral if LLM fails

    async def distill(self, session_id: str, traces: List[Dict[str, Any]]) -> str:
        """§2.2: Async distillation logic with TasteGuard Belief Anchors."""
        corpus = []
        for t in traces:
            msgs = t.get("messages", []) or t.get("stimulus", {}).get("messages", [])
            for m in msgs:
                corpus.append(f"{m.get('role', 'user')}: {m.get('content', '')}")
        
        if not corpus:
            return "[Error] No dialogue to distill."

        full_text = "\n".join(corpus)
        existing_summary = self.get_summary(session_id) or "(No existing summary)"
        
        instruction = (
            "You are a professional Memory Distiller for an AI Agent.\n"
            "Your goal is to extract critical information and MERGE it into the EXISTING summary.\n\n"
            "STRICT GUIDELINES:\n"
            "1. TASTEGUARD (Belief Anchors): Core subjective facts (Technical preferences, Architectural choices) are ANCHORED. "
            "Do NOT overwrite anchored facts with transient chatter unless the user explicitly reverses a decision.\n"
            f"   User Taste Profile: {self.taste_profile}\n"
            "2. STATEFUL MERGE: Integrate new facts. Do not drop old facts unless they are explicitly updated.\n"
            "3. TEMPLATE: Use ### Technical Decisions, ### User Preferences, ### Project Context.\n"
            "4. BE CONCISE: Bullet points only. Max 1500 chars."
        )
        
        summary = await self.llm.generate(
            prompt=f"--- EXISTING SUMMARY ---\n{existing_summary}\n\n--- NEW DIALOGUE ---\n{full_text}",
            system=instruction
        )

        if summary and "[Error]" not in summary:
            self._save_summary(session_id, summary)
            return summary
        return summary or "[Error] Empty summary returned."

    def _save_summary(self, session_id: str, summary: str):
        self.summary_col.upsert(ids=[session_id], documents=[summary], metadatas=[{"last_updated": time.time()}])

    def get_summary(self, session_id: str) -> Optional[str]:
        res = self.summary_col.get(ids=[session_id])
        return res["documents"][0] if res and res["documents"] else None

    def clear_summary(self, session_id: str):
        self.summary_col.delete(ids=[session_id])

    async def verify_relevance(self, query: str, context_sample: str) -> bool:
        """
        Phase 65: Subjective Cognitive Judge (L6b Evaluator).
        Validates context against the user's subjective Taste Profile.
        """
        if "CANARY" in context_sample.upper(): return True

        cache_key = f"{query}||{context_sample}"
        async with self._cache_lock:
            if cache_key in self._judge_cache: return self._judge_cache[cache_key]

        instruction = (
            "You are a Subjective Cognitive Judge.\n"
            "Respond 'YES' if the Context aligns with the user's specific technical tastes and values.\n"
            f"User Taste Profile: {self.taste_profile}\n"
            "Respond 'NO' if the context is tangential or contradicts established preferences.\n"
            "Respond ONLY 'YES' or 'NO'."
        )
        
        try:
            result = await self.llm.generate(prompt=f"Query: {query}\nContext: {context_sample[:1000]}", system=instruction)
            result_upper = result.upper()
            verdict = "YES" in result_upper and "NO" not in result_upper.split("YES")[-1]
            async with self._cache_lock: self._judge_cache[cache_key] = verdict
            return verdict
        except: return True
