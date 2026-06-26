# Generated from design/memory_neocortex.md v1.6 / GEMINI.md Rule 12
import sqlite3
import chromadb
import httpx
import time
import os
import asyncio
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.memory.storage import get_chroma_client
from src.utils.llm_client import LLMFactory, ChatClient
from src.utils.config import get_env

class Neocortex:
    """
    ClawBrain Semantic Distillation Engine.
    v1.4: Updated to use unified ChatClient and LLMFactory.
    v1.6: Segmented Topic Summaries and late-stage snippet filtering.
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
        self.distill_url = self.url
        self.model = distill_model or get_env("CLAWBRAIN_DISTILL_MODEL", "gemma4:e4b")
        self.provider = distill_provider or get_env("CLAWBRAIN_DISTILL_PROVIDER", "ollama")
        self.api_key = get_env("CLAWBRAIN_DISTILL_API_KEY", "")
        
        # v1.4: Use unified ChatClient
        self.llm = LLMFactory.get_chat_client(self.provider, self.url, self.model, self.api_key)

        self._judge_cache = {}
        self._cache_lock = asyncio.Lock()
        self.taste_profile = get_env("CLAWBRAIN_TASTE_PROFILE", "Strict technical accuracy. No conversational filler.")

    async def distill(self, session_id: str, traces: List[Dict[str, Any]], room_id: str = "general") -> str:
        """§2.2: Async distillation logic with recursive knowledge merging (Phase 40)."""
        corpus = []
        for t in traces:
            msgs = t.get("messages", []) or t.get("stimulus", {}).get("messages", [])
            for m in msgs:
                corpus.append(f"{m.get('role', 'user')}: {m.get('content', '')}")
        
        if not corpus: return "[Error] No dialogue to distill."

        full_text = "\n".join(corpus)
        existing_summary = self.get_summary(session_id, room_id=room_id) or "(No existing summary)"
        
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
            self._save_summary(session_id, summary, room_id=room_id)
            return summary
        return summary or "[Error] Empty summary."

    def _save_summary(self, session_id: str, summary: str, room_id: str = "general"):
        summary_id = f"{session_id}::{room_id}" if room_id else session_id
        self.summary_col.upsert(
            ids=[summary_id],
            documents=[summary],
            metadatas=[{"session_id": session_id, "room_id": room_id, "last_updated": time.time()}]
        )

    def get_summary(self, session_id: str, room_id: str = "general") -> Optional[str]:
        summary_id = f"{session_id}::{room_id}" if room_id else session_id
        res = self.summary_col.get(ids=[summary_id])
        if res and res["documents"]: return res["documents"][0]
        # Fallback to general room if not found
        if room_id and room_id != "general":
            res = self.summary_col.get(ids=[f"{session_id}::general"])
            if res and res["documents"]: return res["documents"][0]
        return None

    def clear_summary(self, session_id: str, room_id: str = "general"):
        summary_id = f"{session_id}::{room_id}" if room_id else session_id
        self.summary_col.delete(ids=[summary_id])

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

    async def filter_relevant_snippets(self, query: str, snippets: List[str]) -> List[int]:
        """Ask LLM Grounding Judge to filter out irrelevant snippets individually, returning the indices of relevant ones."""
        if not snippets: return []
        
        snippet_blocks = []
        for idx, s in enumerate(snippets):
            snippet_blocks.append(f"SNIPPET {idx}:\n{s[:800]}")
            
        candidates_str = "\n\n".join(snippet_blocks)
        
        instruction = (
            "You are a Grounding Judge. Evaluate which of the snippets are relevant to the USER QUERY.\n"
            "Be generous: if there is a logical or technical connection, mark the snippet as relevant.\n"
            "Respond ONLY with a JSON list of integers containing the indices of relevant snippets, e.g. [0, 2]."
        )
        prompt = f"USER QUERY: {query}\n\nCANDIDATES:\n{candidates_str}"
        
        try:
            result = await self.llm.generate(prompt=prompt, system=instruction)
            match = re.search(r"\[\s*\d*\s*(?:,\s*\d*\s*)*\]", result or "")
            if match:
                indices = json.loads(match.group(0))
                return [int(i) for i in indices if 0 <= int(i) < len(snippets)]
            ints = [int(i) for i in re.findall(r"\d+", result or "")]
            valid_ints = [i for i in ints if 0 <= i < len(snippets)]
            if valid_ints: return list(set(valid_ints))
        except Exception as e:
            logger.warning(f"[NEOCORTEX] Snippet filtering failed: {e}")
            
        return list(range(len(snippets)))
