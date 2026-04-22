# Generated from design/memory_neocortex.md v2.1 / GEMINI.md Rule 12
import httpx
import time
import os
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.memory.storage import get_chroma_client, Hippocampus
from src.utils.llm_client import LLMClient

logger = logging.getLogger("GATEWAY.MEMORY.NEOCORTEX")

class Neocortex:
    """
    ClawBrain Semantic Distillation Engine.
    Rule 12: Unified session_id terminology enforced.
    """
    def __init__(self, db_dir: str = None, distill_url: str = None, distill_model: str = None, 
                 distill_provider: str = None, hippo: Any = None):
        if db_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "data")
            
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # Phase 33: ChromaDB summaries
        self.chroma_path = self.db_dir / "chroma"
        self.client = get_chroma_client(self.chroma_path)
        self.summary_col = self.client.get_or_create_collection(name="summaries")
        
        # v0.2: Storage handle for thoughts
        self.hippo = hippo or Hippocampus(str(self.db_dir))
        
        # v0.2.1: Unified LLM Client
        self.llm = LLMClient(
            url=os.getenv("CLAWBRAIN_DISTILL_URL", distill_url or "http://127.0.0.1:11434"),
            model=os.getenv("CLAWBRAIN_DISTILL_MODEL", distill_model or "gemma4:e4b"),
            provider=os.getenv("CLAWBRAIN_DISTILL_PROVIDER", distill_provider or "ollama")
        )

    @property
    def distill_url(self):
        return self.llm.url

    async def verify_relevance(self, query: str, context: str) -> bool:
        """Phase 55: Cognitive Judge (v1.23)."""
        prompt = f"Query: {query}\nContext: {context}\n\nVerdict (YES/NO):"
        system = "You are a Cognitive Judge. Determine if the provided context is RELEVANT to the user query. Respond with ONLY 'YES' or 'NO'."
        
        try:
            resp = await self.llm.generate(prompt, system_prompt=system, timeout=10.0)
            return "YES" in resp.message.content.upper()
        except:
            return True # Fail-open

    async def distill(self, session_id: str, traces: List[Dict[str, Any]]) -> str:
        """v0.2: Extract granular 'Thoughts' from dialogue with Root Source Mapping."""
        corpus = []
        for t in traces:
            trace_id = t.get("trace_id")
            if not trace_id: continue
            
            p = t.get("payload") or t
            msgs = p.get("messages", []) or p.get("stimulus", {}).get("messages", [])
            for m in msgs:
                corpus.append(f"[{trace_id}] {m.get('role', 'user')}: {m.get('content', '')}")
        
        if not corpus: return "[Error] No dialogue to distill."
        full_text = "\n".join(corpus)
        
        system = (
            "Extract high-level 'Thoughts' and 'Insights' from dialogue.\n"
            "You MUST return a JSON list of objects: [{\"thought\": \"...\", \"source_traces\": [\"trace-1\"], \"confidence\": 0.9}]."
        )
        prompt = f"--- DIALOGUE ---\n{full_text}\n\nExtract thoughts in JSON:"
        
        try:
            resp = await self.llm.generate(prompt, system_prompt=system, json_mode=True)
            data = self.llm.parse_json(resp.message.content)
            
            thoughts = []
            if isinstance(data, list): thoughts = data
            elif isinstance(data, dict):
                if "thoughts" in data: thoughts = data["thoughts"]
                else: thoughts = [data]

            if thoughts:
                for t in thoughts:
                    text = t.get("thought")
                    sources = t.get("source_traces", []) or ["unknown-source"]
                    if text:
                        self.hippo.upsert_thought(session_id, text, sources, t.get("confidence", 1.0))
                return f"extracted {len(thoughts)} thoughts"
            return "Done"
        except Exception as e:
            logger.warning(f"[NEOCORTEX] Distill fail for {session_id}: {e}")
            return f"[Error] {e}"

    def get_summary(self, session_id: str) -> Optional[str]:
        res = self.summary_col.get(ids=[session_id])
        return res["documents"][0] if res and res["documents"] else None

    def _save_summary(self, session_id: str, summary: str):
        self.summary_col.upsert(ids=[session_id], documents=[summary], metadatas=[{"last_updated": time.time()}])

    def clear_summary(self, session_id: str):
        """v0.2.1: Clear both legacy summary and granular thoughts."""
        try:
            self.summary_col.delete(ids=[session_id])
            self.hippo.thoughts_col.delete(where={"session_id": session_id})
            logger.info(f"[NEOCORTEX] Memory cleared for {session_id}")
        except Exception as e:
            logger.warning(f"[NEOCORTEX] Clear summary failed for {session_id}: {e}")
