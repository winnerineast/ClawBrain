# Generated from design/memory_neocortex.md v1.1
import sqlite3
import httpx
from pathlib import Path
from typing import List, Dict, Any, Optional

class Neocortex:
    """
    ClawBrain 新皮层引擎。
    异步将情节记忆(Trace)提炼为精炼的语义事实(Summary)。
    """
    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data", ollama_url: str = "http://127.0.0.1:11434"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "hippocampus.db"
        self.ollama_url = ollama_url
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS neocortex_summaries (
                    context_id TEXT PRIMARY KEY,
                    summary_text TEXT,
                    last_updated REAL,
                    hebbian_weight REAL DEFAULT 1.0
                )
            """)

    async def distill(self, context_id: str, traces: List[Dict[str, Any]]) -> str:
        if not traces:
            return ""

        dialogue = []
        for t in traces:
            # 提取 Stimulus (User)
            stimulus = t.get("stimulus", {})
            msgs = stimulus.get("messages", []) if isinstance(stimulus, dict) else []
            user_msg = next((m.get("content", "") for m in reversed(msgs) if isinstance(m, dict) and m.get("role") == "user"), "")
            
            # 提取 Reaction (Assistant)
            reaction = t.get("reaction", {})
            if isinstance(reaction, dict):
                ast_msg = reaction.get("message", {}).get("content", "")
            else:
                ast_msg = ""
            
            if user_msg or ast_msg:
                dialogue.append(f"User: {user_msg}\nAssistant: {ast_msg}")

        conversation_text = "\n---\n".join(dialogue)
        
        prompt = (
            "请总结以下对话中的核心技术决策、用户偏好和已解决的问题。\n"
            "以精炼的 Bullet Points 形式输出，严禁废话。\n\n"
            f"对话内容：\n{conversation_text}"
        )

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "gemma4:e4b",
                        "prompt": prompt,
                        "stream": False
                    }
                )
                if response.status_code == 200:
                    summary = response.json().get("response", "").strip()
                    self._save_summary(context_id, summary)
                    return summary
                else:
                    return f"[Error] Distillation failed with status: {response.status_code}"
            except Exception as e:
                return f"[Error] Distillation exception: {str(e)}"

    def _save_summary(self, context_id: str, summary: str):
        import time
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO neocortex_summaries VALUES (?, ?, ?, ?)",
                (context_id, summary, time.time(), 1.0)
            )

    def get_summary(self, context_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute("SELECT summary_text FROM neocortex_summaries WHERE context_id = ?", (context_id,))
                row = cursor.fetchone()
                return row[0] if row else None
            except sqlite3.OperationalError:
                return None
