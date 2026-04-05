# Generated from design/memory_neocortex.md v1.2
import sqlite3
import httpx
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

class Neocortex:
    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data", ollama_url: str = "http://127.0.0.1:11434"):
        # 2.1 准则修正：确保存储目录物理存在，防止 sqlite3 加载失败
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
        """2.2 准则：异步提纯逻辑，支持可配置模型"""
        # 1. 拼接素材
        corpus = []
        for t in traces:
            stimulus = t.get("stimulus", {})
            msgs = stimulus.get("messages", [])
            for m in msgs:
                corpus.append(f"{m.get('role', 'user')}: {m.get('content', '')}")
        
        full_text = "\n".join(corpus)
        prompt = f"请总结以下对话中的核心技术决策、用户偏好和已解决的问题。以精炼的 Bullet Points 形式输出，严禁废话。\n\n对话内容：\n{full_text}"
        
        # 2.2 准则修正：从环境变量获取模型名
        distill_model = os.getenv("CLAWBRAIN_DISTILL_MODEL", "gemma4:e4b")

        # 2. 调用 Ollama
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.ollama_url}/api/generate", json={
                    "model": distill_model,
                    "prompt": prompt,
                    "stream": False
                })
                if resp.status_code != 200:
                    return f"[Error] Distillation failed with status: {resp.status_code}"
                
                summary = resp.json().get("response", "")
                
                # 3. 持久化
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO neocortex_summaries (context_id, summary_text, last_updated)
                        VALUES (?, ?, ?)
                    """, (context_id, summary, time.time()))
                
                return summary
        except Exception as e:
            return f"[Error] Distillation error: {str(e)}"

    def get_summary(self, context_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT summary_text FROM neocortex_summaries WHERE context_id = ?", (context_id,))
            row = cursor.fetchone()
            return row[0] if row else None
