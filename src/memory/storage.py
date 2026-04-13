# Generated from design/memory_hippocampus.md v1.8 / design/memory_working.md v1.4
import sqlite3
import chromadb
import json
import time
import os
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("GATEWAY.MEMORY")

# Phase 33: Shared client cache to prevent "readonly database" errors
# when multiple components (Hippo/Neo) access the same path.
_CHROMA_CLIENTS: Dict[str, chromadb.PersistentClient] = {}

def get_chroma_client(path: Path) -> chromadb.PersistentClient:
    abs_path = str(path.absolute())
    if abs_path not in _CHROMA_CLIENTS:
        _CHROMA_CLIENTS[abs_path] = chromadb.PersistentClient(path=abs_path)
    return _CHROMA_CLIENTS[abs_path]

def clear_chroma_clients():
    """Phase 33: Force clear the client cache (used for tests)."""
    global _CHROMA_CLIENTS
    _CHROMA_CLIENTS = {}

class Hippocampus:
    DEFAULT_THRESHOLD = 512 * 1024

    def __init__(self, db_dir: str = None):
        logger.info(f"[HIPPO] Initializing Hippocampus with db_dir={db_dir}")
        if db_dir is None:
            # Dynamic default path for portability (Issue-003)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "data")
            
        self.db_dir = Path(db_dir)
        self.blob_dir = self.db_dir / "blobs"
        logger.info(f"[HIPPO] Ensuring directories exist: {self.db_dir}, {self.blob_dir}")
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        
        # Phase 33: Switch from SQLite to ChromaDB
        self.chroma_path = self.db_dir / "chroma"
        logger.info(f"[HIPPO] Connecting to ChromaDB at {self.chroma_path}...")
        try:
            self.client = get_chroma_client(self.chroma_path)
            
            # Collections
            logger.info("[HIPPO] Getting/Creating collections: traces, wm_state")
            self.traces_col = self.client.get_or_create_collection(
                name="traces",
                metadata={"hnsw:space": "cosine"}
            )
            self.wm_col = self.client.get_or_create_collection(
                name="wm_state"
            )
            logger.info("[HIPPO] ChromaDB collections ready.")
        except Exception as e:
            logger.exception(f"[HIPPO] CRITICAL: ChromaDB connection failed: {e}")
            raise
        
        # Legacy DB path for cleanup/migration if needed
        self.db_path = self.db_dir / "hippocampus.db"

        # P20: Auto-cleanup dirty data and expired records on startup
        logger.info("[HIPPO] Running startup cleanup...")
        self._startup_cleanup()
        logger.info("[HIPPO] Initialization complete.")

    def _init_db(self):
        """Legacy initialization. Deprecated in favor of ChromaDB collections."""
        pass

    def _startup_cleanup(self):
        """P20: Purge timestamp=0.0 dirty data, TTL expired records, and orphan blob files."""
        logger.info("[HIPPO.CLEANUP] Starting...")
        dirty_count = 0
        expired_count = 0
        orphan_count = 0

        ttl_days = int(os.getenv("CLAWBRAIN_TRACE_TTL_DAYS", "30"))
        cutoff = time.time() - ttl_days * 86400 if ttl_days > 0 else None
        logger.info(f"[HIPPO.CLEANUP] TTL Days: {ttl_days}, Cutoff: {cutoff}")

        # 1. Cleanup ChromaDB
        try:
            # Dirty data
            logger.info("[HIPPO.CLEANUP] Checking for dirty data (timestamp=0.0)...")
            dirty_res = self.traces_col.get(where={"timestamp": 0.0})
            if dirty_res and dirty_res["ids"]:
                dirty_count = len(dirty_res["ids"])
                logger.info(f"[HIPPO.CLEANUP] Deleting {dirty_count} dirty records.")
                self.traces_col.delete(ids=dirty_res["ids"])
            
            # TTL Expired
            if cutoff:
                logger.info(f"[HIPPO.CLEANUP] Checking for expired data (timestamp < {cutoff})...")
                expired_res = self.traces_col.get(where={"timestamp": {"$lt": cutoff}})
                if expired_res and expired_res["ids"]:
                    expired_count = len(expired_res["ids"])
                    logger.info(f"[HIPPO.CLEANUP] Deleting {expired_count} expired records.")
                    # Cleanup blobs first
                    for meta in expired_res["metadatas"]:
                        if meta.get("is_blob") and meta.get("blob_path"):
                            Path(meta["blob_path"]).unlink(missing_ok=True)
                    self.traces_col.delete(ids=expired_res["ids"])
        except Exception as e:
            logger.error(f"[HP_CLEAN] ChromaDB cleanup failed: {e}")

        # 2. Legacy SQLite cleanup
        if os.path.exists(self.db_path):
            logger.info(f"[HIPPO.CLEANUP] Found legacy SQLite DB at {self.db_path}. Cleaning up...")
            with sqlite3.connect(self.db_path) as conn:
                # Reuse the same logic for legacy data
                try:
                    conn.execute("DELETE FROM traces WHERE timestamp = 0.0")
                    if cutoff:
                        conn.execute("DELETE FROM traces WHERE timestamp > 0 AND timestamp < ?", (cutoff,))
                except Exception: pass

        # 3. Orphan blob cleanup (common)
        # We need to collect all valid blob paths from ChromaDB
        logger.info("[HIPPO.CLEANUP] Checking for orphan blobs...")
        try:
            all_metas = self.traces_col.get(include=["metadatas"])["metadatas"]
            valid_paths = {m["blob_path"] for m in all_metas if m.get("is_blob") and m.get("blob_path")}
        except Exception:
            valid_paths = set()

        for blob_file in self.blob_dir.glob("*.json"):
            if str(blob_file.absolute()) not in valid_paths:
                try:
                    blob_file.unlink()
                    orphan_count += 1
                except Exception:
                    pass

        if dirty_count or expired_count or orphan_count:
            logger.info(
                f"[HP_CLEAN] Purged dirty={dirty_count} expired={expired_count} orphan_blobs={orphan_count}"
            )
        logger.info("[HIPPO.CLEANUP] Finished.")

    def save_trace(self, trace_id: str, payload: Dict[str, Any],
                   search_text: str = "", threshold: int = None,
                   context_id: str = "default",
                   room_id: str = "general",
                   state: str = "COMMITTED") -> Dict[str, Any]:
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
        
        # Extract is_complete from reaction if available
        is_complete = True
        if payload and isinstance(payload, dict) and "reaction" in payload and payload["reaction"]:
            is_complete = payload["reaction"].get("is_complete", True)
        
        # Phase 33/34: ChromaDB Storage with Room support
        metadata = {
            "timestamp": now,
            "context_id": context_id,
            "room_id": room_id,
            "model": payload.get("model", ""),
            "trace_id": trace_id,
            "is_blob": 1 if is_blob else 0,
            "blob_path": blob_path,
            "checksum": checksum,
            "is_complete": 1 if is_complete else 0,
            "state": state,
            "raw_content": raw_content # Store full JSON in metadata for fast hydration
        }
        
        # We index the human-readable search_text (intent) as the document 
        # for semantic precision.
        document = search_text if search_text else raw_content
        
        self.traces_col.upsert(
            ids=[trace_id],
            documents=[document],
            metadatas=[metadata]
        )

        return {"trace_id": trace_id, "is_blob": is_blob,
                "blob_path": blob_path, "size": content_size, "checksum": checksum}

    def search(self, query: str, context_id: str = "default", room_id: str = None) -> List[str]:
        """
        Phase 33/34: Semantic Vector Search via ChromaDB.
        Optionally filtered by room_id for higher precision.
        """
        if not query or not query.strip():
            return []
            
        try:
            # Construct metadata filter
            if room_id:
                # ChromaDB requires explicit $and for multiple metadata filters
                where_clause = {
                    "$and": [
                        {"context_id": context_id},
                        {"room_id": room_id}
                    ]
                }
            else:
                where_clause = {"context_id": context_id}

            results = self.traces_col.query(
                query_texts=[query],
                n_results=10,
                where=where_clause
            )
            
            if results and results["ids"]:
                return results["ids"][0]
            return []
        except Exception as e:
            logger.error(f"[CHROMA_SEARCH] Error: {e}")
            return []

    def get_content(self, trace_id: str) -> Optional[str]:
        # Phase 33: Fetch from ChromaDB
        res = self.traces_col.get(ids=[trace_id])
        if not res or not res["metadatas"]:
            # Fallback to legacy SQLite for migration period if needed
            if os.path.exists(self.db_path):
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT is_blob, blob_path, raw_content FROM traces WHERE trace_id = ?",
                        (trace_id,)
                    )
                    row = cursor.fetchone()
                    if row:
                        is_blob, blob_path, raw_content = row
                        if is_blob:
                            try:
                                return Path(blob_path).read_text(encoding="utf-8")
                            except Exception: return None
                        return raw_content
            return None
            
        meta = res["metadatas"][0]
        is_blob = meta.get("is_blob") == 1
        blob_path = meta.get("blob_path")
        
        if is_blob:
            try:
                return Path(blob_path).read_text(encoding="utf-8")
            except Exception:
                return None
        
        # If it's not a blob, the full JSON should be in metadata['raw_content']
        # if it was saved by Phase 33+ logic.
        if "raw_content" in meta and meta["raw_content"]:
            return meta["raw_content"]
            
        # Fallback to document (might be intent or raw_content depending on version)
        return res["documents"][0]

    def get_full_payload(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the complete original payload (stimulus/reaction)."""
        content_str = self.get_content(trace_id)
        if not content_str:
            return None
        try:
            return json.loads(content_str)
        except Exception:
            return None

    def get_recent_traces(self, limit: int, context_id: str = None) -> List[Dict[str, Any]]:
        """Phase 33: Filter and sort by timestamp in Python."""
        where = {"context_id": context_id} if context_id else None
        res = self.traces_col.get(where=where)
        
        if not res or not res["ids"]:
            return []
            
        traces = []
        for i in range(len(res["ids"])):
            meta = res["metadatas"][i]
            # Reconstruct the row-like dict
            trace = {
                "trace_id": res["ids"][i],
                "timestamp": meta.get("timestamp"),
                "model": meta.get("model"),
                "is_blob": meta.get("is_blob"),
                "blob_path": meta.get("blob_path"),
                "raw_content": meta.get("raw_content") or res["documents"][i], 
                "checksum": meta.get("checksum"),
                "context_id": meta.get("context_id"),
                "room_id": meta.get("room_id", "general")
            }
            traces.append(trace)
            
        # Sort by timestamp DESC
        traces.sort(key=lambda x: x["timestamp"] or 0, reverse=True)
        return traces[:limit]

    def get_all_session_ids(self) -> List[str]:
        """Return all known context_ids in the traces collection."""
        res = self.traces_col.get(include=["metadatas"])
        if not res or not res["metadatas"]:
            return []
        
        sids = set()
        for meta in res["metadatas"]:
            if "context_id" in meta:
                sids.add(meta["context_id"])
        return list(sids)

    # ── P22: WorkingMemory Exact Persistence (ChromaDB Version) ──────────────

    def save_wm_state(self, session_id: str, items) -> None:
        """Overwrite the active WM snapshot of the session into wm_col."""
        # Delete existing items for this session
        self.wm_col.delete(where={"session_id": session_id})
        
        ids = []
        docs = []
        metas = []
        
        for item in items:
            uid = f"{session_id}_{item.trace_id}"
            ids.append(uid)
            docs.append(item.content)
            metas.append({
                "session_id": session_id,
                "trace_id": item.trace_id,
                "activation": float(item.activation),
                "timestamp": float(item.timestamp)
            })
            
        if ids:
            self.wm_col.add(ids=ids, documents=docs, metadatas=metas)

    def load_wm_state(self, session_id: str) -> List[Dict[str, Any]]:
        """Read the WM snapshot of the session and return sorted list."""
        res = self.wm_col.get(where={"session_id": session_id})
        if not res or not res["ids"]:
            return []
            
        items = []
        for i in range(len(res["ids"])):
            meta = res["metadatas"][i]
            items.append({
                "trace_id": meta["trace_id"],
                "content": res["documents"][i],
                "activation": meta["activation"],
                "timestamp": meta["timestamp"]
            })
            
        items.sort(key=lambda x: x["timestamp"])
        return items

    def clear_wm_state(self, session_id: str) -> None:
        """Clear the WM snapshot of the specified session."""
        self.wm_col.delete(where={"session_id": session_id})
