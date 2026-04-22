# Generated from design/memory_neocortex.md v1.2 / GEMINI.md Rule 12
import sqlite3
import chromadb
import httpx
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.memory.storage import get_chroma_client, Hippocampus

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
        
        # v0.2: Storage handle for thoughts
        self.hippo = Hippocampus(str(self.db_dir))
        
        # Legacy DB path
        self.db_path = self.db_dir / "hippocampus.db"
        
        # Distillation Config
        self.distill_url = os.getenv("CLAWBRAIN_DISTILL_URL", distill_url or "http://127.0.0.1:11434")
        self.distill_model = os.getenv("CLAWBRAIN_DISTILL_MODEL", distill_model or "gemma4:e4b")
        self.distill_provider = os.getenv("CLAWBRAIN_DISTILL_PROVIDER", distill_provider or "ollama")
        self.api_key = os.getenv("CLAWBRAIN_DISTILL_API_KEY", "")
        
        self.http_client = client

    async def distill(self, session_id: str, traces: List[Dict[str, Any]]) -> str:
        """v0.2: Extract granular 'Thoughts' from dialogue with Root Source Mapping."""
        corpus = []
        trace_ids = []
        for t in traces:
            trace_id = t.get("trace_id")
            if not trace_id: continue
            trace_ids.append(trace_id)
            
            p = t.get("payload") or t
            msgs = p.get("messages", []) or p.get("stimulus", {}).get("messages", [])
            for m in msgs:
                corpus.append(f"[{trace_id}] {m.get('role', 'user')}: {m.get('content', '')}")
        
        if not corpus:
            return "[Error] No dialogue to distill."

        full_text = "\n".join(corpus)
        
        # v0.2: Thought-Retriever Instruction
        instruction = (
            "You are a professional Memory Processor (Neocortex). "
            "Your goal is to extract high-level 'Thoughts' and 'Insights' from the provided dialogue.\n\n"
            "STRICT GUIDELINES:\n"
            "1. EXTRACT GRANULAR THOUGHTS: Identify user preferences, technical decisions, and project context.\n"
            "2. ROOT SOURCE MAPPING: Every thought MUST be mapped to the exact trace IDs (e.g., [trace-123]) that support it.\n"
            "3. JSON OUTPUT ONLY: You MUST return a JSON list of objects.\n\n"
            "   [{\"thought\": \"User prefers Python over Java\", \"source_traces\": [\"trace-1\"], \"confidence\": 0.9}, ...]\n\n"
            "4. BE CONCISE: Only extract critical insights. If no new insights are found, return an empty list [].\n"
            "5. DO NOT provide any explanation outside the JSON."
        )
        prompt = (f"{instruction}\n\n"
                  f"--- NEW DIALOGUE TO PROCESS ---\n{full_text}\n\n"
                  f"JSON Output:")
        
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
                    "stream": False,
                    "format": "json"
                })
            else:
                # Ensure URL is correctly formatted for OpenAI /chat/completions
                url = f"{self.distill_url.rstrip('/')}/chat/completions"
                resp = await client.post(url, headers=headers, json={
                    "model": self.distill_model,
                    "messages": [
                        {"role": "system", "content": "You are a professional memory distiller. Output JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "stream": False
                })
            
            if resp.status_code != 200:
                return f"[Error] Distillation failed ({resp.status_code}): {resp.text}"
            
            if self.distill_provider == "ollama":
                raw_response = resp.json().get("response", "[]")
            else:
                raw_response = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "[]")

            try:
                import json
                import re
                # Clean potential markdown
                clean_text = re.sub(r'```json\s*|\s*```', '', raw_response).strip()
                thoughts = json.loads(clean_text)
                if isinstance(thoughts, dict) and "thoughts" in thoughts:
                    thoughts = thoughts["thoughts"]
                
                if isinstance(thoughts, list):
                    for t in thoughts:
                        thought_text = t.get("thought")
                        sources = t.get("source_traces", [])
                        conf = t.get("confidence", 1.0)
                        if thought_text and sources:
                            self.hippo.upsert_thought(session_id, thought_text, sources, conf)
                    return f"Successfully extracted {len(thoughts)} thoughts."
            except Exception as e:
                return f"[Error] JSON parsing failed: {e} | Raw: {raw_response}"
                
            return "[Error] Empty or invalid thoughts returned from provider."
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
