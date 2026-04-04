# Generated from design/memory_hippocampus.md v1.2
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List

class Hippocampus:
    """
    ClawBrain 海马体存储引擎。
    实现 SQLite FTS5 全文索引与大文件 Blob 流式落盘分流机制。
    """
    BLOB_THRESHOLD = 512 * 1024  # 512KB

    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data"):
        self.db_dir = Path(db_dir)
        self.blob_dir = self.db_dir / "blobs"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.db_dir / "hippocampus.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 元数据表
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
            # 全文检索虚拟表
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_idx USING fts5(
                    trace_id UNINDEXED,
                    content
                )
            """)

    def save_trace(self, trace_id: str, payload: Dict[str, Any], search_text: str = "") -> Dict[str, Any]:
        """
        根据 Payload 大小自动分流落盘。
        """
        content_json = json.dumps(payload)
        content_size = len(content_json.encode('utf-8'))
        is_blob = content_size > self.BLOB_THRESHOLD
        blob_path = ""
        raw_content = ""

        if is_blob:
            # 超过阈值，落入磁盘 Blob
            blob_file = self.blob_dir / f"{trace_id}.json"
            blob_path = str(blob_file.absolute())
            with open(blob_path, "w", encoding="utf-8") as f:
                f.write(content_json)
        else:
            # 小数据，直接入库
            raw_content = content_json

        # 记录元数据
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?)",
                (trace_id, 0.0, payload.get("model", "unknown"), 1 if is_blob else 0, blob_path, raw_content)
            )
            # 建立搜索索引
            if search_text:
                conn.execute(
                    "INSERT INTO search_idx VALUES (?, ?)", 
                    (trace_id, search_text)
                )
        
        # 严格遵守返回契约
        return {
            "trace_id": trace_id,
            "is_blob": is_blob,
            "blob_path": blob_path,
            "size": content_size
        }

    def search(self, query: str) -> List[str]:
        """
        安全的全文检索。
        对查询词进行引号包裹转义，防止特殊字符导致 OperationalError。
        """
        safe_query = f'"{query}"'
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    "SELECT trace_id FROM search_idx WHERE content MATCH ?", 
                    (safe_query,)
                )
                return [row[0] for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                # 容错处理
                return []
