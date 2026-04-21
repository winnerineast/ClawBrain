# Generated from design/memory_neocortex.md v1.2 / GEMINI.md Rule 12
import sqlite3
import chromadb
import httpx
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.memory.storage import get_chroma_client

class Neocortex:
    """
    ClawBrain Semantic Distillation Engine.
    Rule 12: Unified session_id terminology enforced.
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
        self.distill_url = os.getenv("CLAWBRAIN_DISTILL_URL", distill_url or "http://127.0.0.1:11434")
        self.distill_model = os.getenv("CLAWBRAIN_DISTILL_MODEL", distill_model or "gemma4:e4b")
        self.distill_provider = os.getenv("CLAWBRAIN_DISTILL_PROVIDER", distill_provider or "ollama")
        self.api_key = os.getenv("CLAWBRAIN_DISTILL_API_KEY", "")
        
        self.http_client = client

    async def distill(self, session_id: str, traces: List[Dict[str, Any]]) -> str:
        """§2.2: Async distillation logic with recursive knowledge merging (Phase 40)."""
        corpus = []
        for t in traces:
            # P47: Robust extraction from stimulus (ingest) or top-level (direct)
            msgs = t.get("messages", []) or t.get("stimulus", {}).get("messages", [])
            for m in msgs:
                corpus.append(f"{m.get('role', 'user')}: {m.get('content', '')}")
        
        if not corpus:
            return "[Error] No dialogue to distill."

        full_text = "\n".join(corpus)
        existing_summary = self.get_summary(session_id) or "(No existing summary)"
        
        # Phase 40: Recursive Summarization Instruction
        instruction = (
            "You are a professional Memory Distiller for an AI Agent. "
            "Your goal is to extract critical information from a NEW dialogue and MERGE it into the EXISTING summary.\n\n"
            "STRICT GUIDELINES:\n"
            "1. PRESERVE TECHNICAL IDENTIFIERS: Always keep exact FQDNs, IP addresses, Port numbers, and Database names.\n"
            "2. STATEFUL MERGE: Integrate new facts from the dialogue into the existing summary below. "
            "Do not drop old facts unless they are explicitly contradicted/updated by the new dialogue.\n"
            "3. REQUIRED TEMPLATE: You MUST output the summary strictly using the following Markdown template. "
            "Do not output categories that have no facts.\n\n"
            "   ### Technical Decisions\n"
            "   - [Technical details, URLs, IPs, architecture]\n"
            "   ### User Preferences\n"
            "   - [User preferences, workflow habits, styling]\n"
            "   ### Project Context\n"
            "   - [General context, names, goals]\n"
            "   ### Relationships\n"
            "   - [People, roles, teams]\n\n"
            "4. BE CONCISE: Use Bullet Points. Max total length: 1500 characters.\n"
            "5. EVOLUTION: If a fact is updated in the dialogue, only preserve the NEWEST value."
        )
        prompt = (f"{instruction}\n\n"
                  f"--- EXISTING SUMMARY ---\n{existing_summary}\n\n"
                  f"--- NEW DIALOGUE TO DISTILL ---\n{full_text}")
        
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            if self.http_client:
                return await self._dispatch_request(self.http_client, headers, prompt, session_id)
            else:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    return await self._dispatch_request(client, headers, prompt, session_id)
                
        except Exception as e:
            return f"[Error] Distillation connection error: {str(e)}"

    async def _dispatch_request(self, client: httpx.AsyncClient, headers: Dict, prompt: str, session_id: str) -> str:
        try:
            if self.distill_provider == "ollama":
                # Ensure URL is correctly formatted for Ollama /api/generate
                url = f"{self.distill_url.rstrip('/')}/api/generate"
                resp = await client.post(url, headers=headers, json={
                    "model": self.distill_model,
                    "prompt": prompt,
                    "stream": False
                })
            else:
                # Ensure URL is correctly formatted for OpenAI /chat/completions
                url = f"{self.distill_url.rstrip('/')}/chat/completions"
                resp = await client.post(url, headers=headers, json={
                    "model": self.distill_model,
                    "messages": [
                        {"role": "system", "content": "You are a professional memory distiller."},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                })
            
            if resp.status_code != 200:
                return f"[Error] Distillation failed ({resp.status_code}): {resp.text}"
            
            if self.distill_provider == "ollama":
                summary = resp.json().get("response", "")
            else:
                summary = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")

            if summary:
                self._save_summary(session_id, summary)
                return summary
            return "[Error] Empty summary returned from provider."
        except Exception as e:
            return f"[Error] Distillation connection error: {str(e)}"

    def _save_summary(self, session_id: str, summary: str):
        """Phase 33: Summary persistence in ChromaDB."""
        self.summary_col.upsert(
            ids=[session_id],
            documents=[summary],
            metadatas=[{"last_updated": time.time()}]
        )

    def get_summary(self, session_id: str) -> Optional[str]:
        res = self.summary_col.get(ids=[session_id])
        if res and res["documents"]:
            return res["documents"][0]
            
        # Legacy fallback
        if os.path.exists(self.db_path):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT summary_text FROM neocortex_summaries WHERE session_id = ?", (session_id,))
                    row = cursor.fetchone()
                    return row[0] if row else None
            except Exception: pass
        return None

    def clear_summary(self, session_id: str):
        """P17 Management API: Clear Neocortex summary."""
        self.summary_col.delete(ids=[session_id])

    async def verify_relevance(self, query: str, context_sample: str) -> bool:
        """Phase 55: Cognitive Judge (v1.3). Verify if context truly addresses the query."""
        instruction = (
            "You are a Grounding Judge. Your task is to decide if the provided CONTEXT contains "
            "facts that are actually relevant to the USER QUERY. "
            "Ignore general similarity; look for factual utility.\n"
            "Respond ONLY with 'YES' or 'NO'."
        )
        prompt = f"USER QUERY: {query}\n\nCONTEXT SAMPLE:\n{context_sample[:1000]}"
        
        try:
            # Re-use the distillation infrastructure for speed
            headers = {}
            if self.api_key: headers["Authorization"] = f"Bearer {self.api_key}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                if self.distill_provider == "ollama":
                    url = f"{self.distill_url.rstrip('/')}/api/generate"
                    resp = await client.post(url, headers=headers, json={
                        "model": self.distill_model,
                        "prompt": f"{instruction}\n\n{prompt}",
                        "stream": False
                    })
                    result = resp.json().get("response", "").strip().upper()
                else:
                    url = f"{self.distill_url.rstrip('/')}/chat/completions"
                    resp = await client.post(url, headers=headers, json={
                        "model": self.distill_model,
                        "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": prompt}],
                        "stream": False
                    })
                    result = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip().upper()
                
                return "YES" in result
        except Exception as e:
            # On error, default to True to avoid losing memory (fail-open)
            return True
