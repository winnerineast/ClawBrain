# Generated from design/memory_neocortex.md v1.4 / GEMINI.md Rule 12
import sqlite3
import chromadb
import httpx
import time
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.memory.storage import get_chroma_client
from src.utils.llm_client import LLMFactory, ChatClient
from src.utils.config import get_env

class Neocortex:
    """
    ClawBrain Semantic Distillation Engine.
    v1.4: Updated to use unified ChatClient and LLMFactory.
    """
    def __init__(self, db_dir: str = None, distill_url: str = None, distill_model: str = None, 
                 distill_provider: str = None):
        if db_dir is None:
            db_dir = get_env("CLAWBRAIN_DB_DIR", os.path.join(os.getcwd(), "data"))
            
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # Phase 33: ChromaDB summaries
        self.chroma_path = self.db_dir / "chroma"
        self.client = get_chroma_client(self.chroma_path)
        self.summary_col = self.client.get_or_create_collection(name="summaries")
        
        # Legacy DB path
        self.db_path = self.db_dir / "hippocampus.db"
        
        # Distillation Config
        self.url = distill_url or get_env("CLAWBRAIN_DISTILL_URL", "http://127.0.0.1:11434")
        self.model = distill_model or get_env("CLAWBRAIN_DISTILL_MODEL", "gemma4:e4b")
        self.provider = distill_provider or get_env("CLAWBRAIN_DISTILL_PROVIDER", "ollama")
        self.api_key = get_env("CLAWBRAIN_DISTILL_API_KEY", "")
        
        # v1.4: Use unified ChatClient
        self.llm = LLMFactory.get_chat_client(self.provider, self.url, self.model, self.api_key)

        self._judge_cache = {}
        self._cache_lock = asyncio.Lock()
        self.taste_profile = get_env("CLAWBRAIN_TASTE_PROFILE", "Strict technical accuracy. No conversational filler.")

    async def distill(self, session_id: str, traces: List[Dict[str, Any]]) -> str:
        """§2.2: Async distillation logic with recursive knowledge merging (Phase 40)."""
        corpus = []
        for t in traces:
            msgs = t.get("messages", []) or t.get("stimulus", {}).get("messages", [])
            for m in msgs:
                corpus.append(f"{m.get('role', 'user')}: {m.get('content', '')}")
        
        if not corpus: return "[Error] No dialogue to distill."

        full_text = "\n".join(corpus)
        existing_summary = self.get_summary(session_id) or "(No existing summary)"
        
        instruction = (
            "You are a professional Memory Distiller. Merge NEW dialogue into the EXISTING summary.\n"
            f"STYLE ANCHOR: {self.taste_profile}\n\n"
            "STRICT GUIDELINES:\n"
            "1. PRESERVE TECHNICAL IDENTIFIERS: Keep exact FQDNs, IPs, Ports.\n"
            "2. STATEFUL MERGE: Integrate facts without dropping old ones unless contradicted.\n"
            "3. REQUIRED TEMPLATE: Use ### Technical Decisions, ### User Preferences, ### Project Context.\n"
            "4. CONCISE: Use Bullet Points. Max 1500 chars."
        )
        
        summary = await self.llm.generate(
            prompt=f"--- EXISTING SUMMARY ---\n{existing_summary}\n\n--- NEW DIALOGUE ---\n{full_text}",
            system=instruction
        )

        if summary and "[Error]" not in summary:
            self._save_summary(session_id, summary)
            return summary
        return summary or "[Error] Empty summary."

    def _save_summary(self, session_id: str, summary: str):
        self.summary_col.upsert(
            ids=[session_id],
            documents=[summary],
            metadatas=[{"last_updated": time.time()}]
        )

    def get_summary(self, session_id: str) -> Optional[str]:
        res = self.summary_col.get(ids=[session_id])
        if res and res["documents"]: return res["documents"][0]
        return None

    def clear_summary(self, session_id: str):
        self.summary_col.delete(ids=[session_id])

    async def verify_relevance(self, query: str, context_sample: str) -> bool:
        instruction = (
            "You are a Grounding Judge. Decide if the CONTEXT contains information relevant to the USER QUERY.\n"
            "Be generous: if there is a logical or technical connection, respond with 'YES'.\n"
            "Respond ONLY with 'YES' or 'NO'."
        )
        prompt = f"USER QUERY: {query}\n\nCONTEXT SAMPLE:\n{context_sample[:1000]}"
        
        try:
            result = await self.llm.generate(prompt=prompt, system=instruction)
            return "YES" in (result or "").upper()
        except Exception:
            return True # Fail-open
