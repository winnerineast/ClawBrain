# Generated from design/memory_neocortex.md v1.0
import sqlite3
import json
import httpx
from typing import List, Dict, Any, Optional
from pathlib import Path

class Neocortex:
    """
    ClawBrain 新皮层引擎。
    负责慢速语义整合，将情节记忆提炼为精华事实。
    """
    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data", ollama_url: str = "http://127.0.0.1:11434"):
        self.db_path = Path(db_dir) / "hippocampus.db"
        self.ollama_url = ollama_url
        self._init_neocortex_table()

    def _init_neocortex_table(self):
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
        """
        核心泛化算法：调用 LLM 提炼摘要。
        """
        # 构建提炼 Prompt
        conversation_text = "\n".join([
            f"User: {t.get('stimulus', {}).get('messages', [{}])[-1].get('content', '')}\n"
            f"Assistant: {t.get('reaction', {}).get('message', {}).get('content', '')}"
            for t in traces
        ])
        
        prompt = f"""请总结以下对话中的核心技术决策、用户偏好和已解决的问题。
以精炼的 Bullet Points 形式输出，严禁废话。

对话内容：
{conversation_text}
"""

        # 2.2 准则：调用轻量级任务
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "gemma4:e4b", # 使用快速的 MoE 模型进行摘要
                        "prompt": prompt,
                        "stream": False
                    }
                )
                if response.status_code == 200:
                    summary = response.json().get("response", "").strip()
                    # 2.3 准则：存储至新皮层
                    self._save_summary(context_id, summary)
                    return summary
            except Exception as e:
                return f"Distillation failed: {str(e)}"
        return ""

    def _save_summary(self, context_id: str, summary: str):
        import time
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO neocortex_summaries VALUES (?, ?, ?, ?)",
                (context_id, summary, time.time(), 1.0)
            )

    def get_summary(self, context_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT summary_text FROM neocortex_summaries WHERE context_id = ?", (context_id,))
            row = cursor.fetchone()
            return row[0] if row else None
