# Generated from design/memory_hippocampus.md v1.3
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List

class Hippocampus:
    DEFAULT_THRESHOLD = 512 * 1024

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
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search_idx USING fts5(trace_id UNINDEXED, content)")

    def save_trace(self, trace_id: str, payload: Dict[str, Any], search_text: str = "", threshold: int = None) -> Dict[str, Any]:
        content_json = json.dumps(payload)
        content_size = len(content_json.encode('utf-8'))
        
        # 2.2 准则：基于模型窗口动态判定分流
        limit = threshold if threshold is not None else self.DEFAULT_THRESHOLD
        is_blob = content_size > limit
        
        blob_path = ""
        raw_content = ""

        if is_blob:
            blob_file = self.blob_dir / f"{trace_id}.json"
            blob_path = str(blob_file.absolute())
            with open(blob_path, "w", encoding="utf-8") as f:
                f.write(content_json)
        else:
            raw_content = content_json

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?)",
                        (trace_id, 0.0, payload.get("model", ""), 1 if is_blob else 0, blob_path, raw_content))
            if search_text:
                conn.execute("INSERT INTO search_idx VALUES (?, ?)", (trace_id, search_text))
        
        return {"trace_id": trace_id, "is_blob": is_blob, "blob_path": blob_path, "size": content_size}

    def search(self, query: str) -> List[str]:
        safe_query = f'"{query}"'
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute("SELECT trace_id FROM search_idx WHERE content MATCH ?", (safe_query,))
                return [row[0] for row in cursor.fetchall()]
            except: return []
