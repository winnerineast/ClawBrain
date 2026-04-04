# Generated from design/memory_hippocampus.md v1.1
import sqlite3
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

class Hippocampus:
    BLOB_THRESHOLD = 512 * 1024

    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data"):
        self.db_dir = Path(db_dir)
        self.blob_dir = self.db_dir / "blobs"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "hippocampus.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    timestamp REAL,
                    model TEXT,
                    is_blob INTEGER,
                    blob_path TEXT,
                    raw_content TEXT
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_idx USING fts5(
                    trace_id UNINDEXED,
                    content
                )
            """)

    def save_trace(self, trace_id: str, payload: Dict[str, Any], search_text: str = ""):
        content_json = json.dumps(payload)
        content_size = len(content_json)
        is_blob = content_size > self.BLOB_THRESHOLD
        blob_path = ""

        if is_blob:
            blob_file = self.blob_dir / f"{trace_id}.json"
            with open(blob_file, "w") as f:
                f.write(content_json)
            blob_path = str(blob_file)
            raw_content = ""
        else:
            raw_content = content_json

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO traces VALUES (?, ?, ?, ?, ?, ?)",
                (trace_id, 0.0, payload.get("model", ""), 1 if is_blob else 0, blob_path, raw_content)
            )
            if search_text:
                conn.execute("INSERT INTO search_idx VALUES (?, ?)", (trace_id, search_text))
        
        # 2.1 准则：遵守返回契约
        return {
            "trace_id": trace_id,
            "is_blob": is_blob,
            "blob_path": blob_path,
            "size": content_size
        }

    def search(self, query: str) -> List[str]:
        """执行全文检索 (带安全过滤)"""
        # 2.2 准则：对查询词加引号，防止 FTS5 解析连字符错误
        safe_query = f'"{query}"'
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    "SELECT trace_id FROM search_idx WHERE content MATCH ?", (safe_query,)
                )
                return [row[0] for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                return []
