# Generated from design/memory_neocortex.md v1.2 / design/management_api.md v1.0
import sqlite3
import chromadb
import httpx
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.memory.storage import get_chroma_client

class Neocortex:
    def __init__(self, db_dir: str = None, distill_url: str = None, distill_model: str = None, distill_provider: str = None):
        if db_dir is None:
            # Dynamic default path for portability (Issue-003)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "data")
            
        # §2.1: Ensure storage directory exists
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # Phase 33: ChromaDB summaries
        self.chroma_path = self.db_dir / "chroma"
        self.client = get_chroma_client(self.chroma_path)
        self.summary_col = self.client.get_or_create_collection(name="summaries")
        
        # Legacy DB path for migration period
        self.db_path = self.db_dir / "hippocampus.db"
        
        # §2.1 & ISSUE-004: Dynamic Distillation Config
        # Priority: Env Var > Constructor Argument > Default
        self.distill_url = os.getenv("CLAWBRAIN_DISTILL_URL", distill_url or "http://127.0.0.1:11434")
        self.distill_model = os.getenv("CLAWBRAIN_DISTILL_MODEL", distill_model or "gemma4:e4b")
        self.distill_provider = os.getenv("CLAWBRAIN_DISTILL_PROVIDER", distill_provider or "ollama")
        self.api_key = os.getenv("CLAWBRAIN_DISTILL_API_KEY", "")
        
        self._init_db()

    def _init_db(self):
        """Legacy initialization. Deprecated in favor of ChromaDB."""
        pass

    async def distill(self, context_id: str, traces: List[Dict[str, Any]]) -> str:
        """§2.2: Async distillation logic with universal provider support (ISSUE-004)."""
        # 1. Prepare corpus
        corpus = []
        for t in traces:
            stimulus = t.get("stimulus", {})
            msgs = stimulus.get("messages", [])
            for m in msgs:
                corpus.append(f"{m.get('role', 'user')}: {m.get('content', '')}")
        
        full_text = "\n".join(corpus)
        # Phase 32 (ISSUE-007): Structured template-based distillation instruction
        instruction = (
            "You are a professional Memory Distiller for an AI Agent. "
            "Your goal is to extract and preserve critical information from the following dialogue into a concise summary.\n\n"
            "STRICT GUIDELINES:\n"
            "1. PRESERVE TECHNICAL IDENTIFIERS: Always keep exact FQDNs, IP addresses, Port numbers, and Database names.\n"
            "2. REQUIRED TEMPLATE: You MUST output the summary strictly using the following Markdown template. "
            "Do not output categories that have no facts.\n\n"
            "   ### Technical Decisions\n"
            "   - [Technical details, URLs, IPs, architecture]\n"
            "   ### User Preferences\n"
            "   - [User preferences, workflow habits, styling]\n"
            "   ### Project Context\n"
            "   - [General context, names, goals]\n"
            "   ### Relationships\n"
            "   - [People, roles, teams]\n\n"
            "3. BE CONCISE: Use Bullet Points. No conversational filler or introductory text.\n"
            "4. EVOLUTION: If a fact is updated in the dialogue, only preserve the NEWEST value."
        )
        prompt = f"{instruction}\n\nDialogue to Distill:\n{full_text}"
        
        # 2. Dispatch by provider
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=90.0) as client:
                if self.distill_provider == "ollama":
                    # Ollama specific protocol
                    resp = await client.post(f"{self.distill_url}/api/generate", headers=headers, json={
                        "model": self.distill_model,
                        "prompt": prompt,
                        "stream": False
                    })
                    if resp.status_code != 200:
                        return f"[Error] Ollama Distillation failed ({resp.status_code}): {resp.text}"
                    summary = resp.json().get("response", "")
                else:
                    # Default to OpenAI-compatible Chat Completion protocol (OMLX, LM Studio, Cloud)
                    resp = await client.post(f"{self.distill_url}/chat/completions", headers=headers, json={
                        "model": self.distill_model,
                        "messages": [
                            {"role": "system", "content": "You are a professional memory distiller."},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    })
                    if resp.status_code != 200:
                        return f"[Error] OpenAI-compatible Distillation failed ({resp.status_code}): {resp.text}"
                    summary = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")

                if summary:
                    self._save_summary(context_id, summary)
                    return summary
                return "[Error] Empty summary returned from provider."
                
        except Exception as e:
            return f"[Error] Distillation connection error: {str(e)}"

    def _save_summary(self, context_id: str, summary: str):
        """Phase 33: Summary persistence in ChromaDB."""
        self.summary_col.upsert(
            ids=[context_id],
            documents=[summary],
            metadatas=[{"last_updated": time.time()}]
        )

    def get_summary(self, context_id: str) -> Optional[str]:
        # Phase 33: Fetch from ChromaDB
        res = self.summary_col.get(ids=[context_id])
        if res and res["documents"]:
            return res["documents"][0]
            
        # Legacy fallback
        if os.path.exists(self.db_path):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT summary_text FROM neocortex_summaries WHERE context_id = ?", (context_id,))
                    row = cursor.fetchone()
                    return row[0] if row else None
            except Exception: pass
        return None

    def clear_summary(self, context_id: str):
        """P17 Management API: Clear Neocortex summary for a specific session."""
        self.summary_col.delete(ids=[context_id])
