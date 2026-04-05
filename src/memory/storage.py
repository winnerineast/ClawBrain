# Generated from design/memory_hippocampus.md v1.5
import sqlite3
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional

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
                    raw_content TEXT,
                    checksum TEXT
                )
            """)
            # 兼容性处理：如果表已存在但缺少 checksum 字段，则添加
            try:
                conn.execute("ALTER TABLE traces ADD COLUMN checksum TEXT")
            except sqlite3.OperationalError:
                pass
                
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search_idx USING fts5(trace_id UNINDEXED, content)")

    def save_trace(self, trace_id: str, payload: Dict[str, Any], search_text: str = "", threshold: int = None) -> Dict[str, Any]:
        content_json = json.dumps(payload)
        content_bytes = content_json.encode('utf-8')
        content_size = len(content_bytes)
        
        # 2.2 准则修正：计算 SHA-256 校验和 (Fixed Bug 7)
        checksum = hashlib.sha256(content_bytes).hexdigest()
        
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

        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (trace_id, now, payload.get("model", ""), 1 if is_blob else 0, blob_path, raw_content, checksum))
            if search_text:
                conn.execute("INSERT INTO search_idx VALUES (?, ?)", (trace_id, search_text))
        
        return {
            "trace_id": trace_id, 
            "is_blob": is_blob, 
            "blob_path": blob_path, 
            "size": content_size,
            "checksum": checksum
        }

    def search(self, query: str) -> List[str]:
        safe_query = f'"{query}"'
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute("SELECT trace_id FROM search_idx WHERE content MATCH ?", (safe_query,))
                return [row[0] for row in cursor.fetchall()]
            except: return []

    def get_content(self, trace_id: str) -> Optional[str]:
        """2.4 准则：根据 ID 提取内容，支持 BLOB 自动透明化"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT is_blob, blob_path, raw_content FROM traces WHERE trace_id = ?", (trace_id,))
            row = cursor.fetchone()
            if not row: return None
            
            is_blob, blob_path, raw_content = row
            if is_blob:
                try: return Path(blob_path).read_text(encoding="utf-8")
                except: return None
            return raw_content

    def get_recent_traces(self, limit: int) -> List[Dict[str, Any]]:
        """2.4 准则：时序检索，支持提纯准备"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM traces ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
