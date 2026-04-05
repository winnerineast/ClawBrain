# Generated from design/memory_hippocampus.md v1.7
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
            # traces 表
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
            # P15: checksum 列兼容迁移
            try:
                conn.execute("ALTER TABLE traces ADD COLUMN checksum TEXT")
            except sqlite3.OperationalError:
                pass
            # P18: context_id 列兼容迁移
            try:
                conn.execute("ALTER TABLE traces ADD COLUMN context_id TEXT DEFAULT 'default'")
            except sqlite3.OperationalError:
                pass

            # P18: search_idx 需要含 context_id 列，检测旧 schema 并按需重建
            needs_rebuild = False
            try:
                conn.execute("SELECT context_id FROM search_idx LIMIT 1")
            except sqlite3.OperationalError:
                needs_rebuild = True

            if needs_rebuild:
                conn.execute("DROP TABLE IF EXISTS search_idx")

            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_idx
                USING fts5(trace_id UNINDEXED, context_id UNINDEXED, content)
            """)

    def save_trace(self, trace_id: str, payload: Dict[str, Any],
                   search_text: str = "", threshold: int = None,
                   context_id: str = "default") -> Dict[str, Any]:
        content_json = json.dumps(payload)
        content_bytes = content_json.encode('utf-8')
        content_size = len(content_bytes)
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
            conn.execute(
                "INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (trace_id, now, payload.get("model", ""),
                 1 if is_blob else 0, blob_path, raw_content, checksum, context_id)
            )
            if search_text:
                conn.execute(
                    "INSERT INTO search_idx VALUES (?, ?, ?)",
                    (trace_id, context_id, search_text)
                )

        return {"trace_id": trace_id, "is_blob": is_blob,
                "blob_path": blob_path, "size": content_size, "checksum": checksum}

    def search(self, query: str, context_id: str = "default") -> List[str]:
        """
        两级降级搜索，严格按 context_id 隔离 (P15 + P18)。
        """
        if not query or not query.strip():
            return []
        with sqlite3.connect(self.db_path) as conn:
            # Level 1: 精确短语 + session 过滤
            try:
                cursor = conn.execute(
                    "SELECT trace_id FROM search_idx WHERE content MATCH ? AND context_id = ?",
                    (f'"{query}"', context_id)
                )
                results = [row[0] for row in cursor.fetchall()]
                if results:
                    return results
            except sqlite3.OperationalError:
                pass

            # Level 2: 关键词 AND + session 过滤
            try:
                special = set('"*^()[]{}: ')
                keywords = [
                    w for w in query.split()
                    if len(w) > 2 and not any(c in special for c in w)
                ][:5]
                if not keywords:
                    return []
                fts_query = " ".join(f'"{k}"' for k in keywords)
                cursor = conn.execute(
                    "SELECT trace_id FROM search_idx WHERE content MATCH ? AND context_id = ?",
                    (fts_query, context_id)
                )
                return [row[0] for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                return []

    def get_content(self, trace_id: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT is_blob, blob_path, raw_content FROM traces WHERE trace_id = ?",
                (trace_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            is_blob, blob_path, raw_content = row
            if is_blob:
                try:
                    return Path(blob_path).read_text(encoding="utf-8")
                except:
                    return None
            return raw_content

    def get_recent_traces(self, limit: int, context_id: str = None) -> List[Dict[str, Any]]:
        """按 session 过滤最近记录 (P18 新增 context_id 参数)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if context_id:
                cursor = conn.execute(
                    "SELECT * FROM traces WHERE context_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (context_id, limit)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM traces ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_session_ids(self) -> List[str]:
        """返回 traces 表中所有已知的 context_id（用于 hydrate）"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    "SELECT DISTINCT context_id FROM traces WHERE context_id IS NOT NULL"
                )
                return [row[0] for row in cursor.fetchall()]
            except:
                return []
