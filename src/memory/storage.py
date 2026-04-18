# Generated from design/memory_hippocampus.md v1.9 / GEMINI.md Rule 12
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

def get_chroma_client(db_path: Path):
    return chromadb.PersistentClient(path=str(db_path))

class Hippocampus:
    """
    ClawBrain Episodic Memory Engine.
    Uses ChromaDB for semantic search and tiered blob storage for large payloads.
    Rule 12: Unified session_id terminology enforced.
    """
    def __init__(self, db_dir: str):
        self.db_dir = Path(db_dir)
        self.chroma_path = self.db_dir / "chroma"
        self.blob_dir = self.db_dir / "blobs"
        
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.client = get_chroma_client(self.chroma_path)
            # Collection 1: Episodic traces
            self.traces_col = self.client.get_or_create_collection(
                name="traces",
                metadata={"hnsw:space": "cosine"}
            )
            # Collection 2: Working memory snapshots
            self.wm_col = self.client.get_or_create_collection(
                name="wm_state"
            )
            # Collection 3: Flattened Entity Registry
            self.entities_col = self.client.get_or_create_collection(
                name="entities"
            )
            logger.info("[HIPPO] ChromaDB collections ready (session_id compliant).")
            
            # P20: Run startup cleanup logic
            self._startup_cleanup()
            
        except Exception as e:
            logger.exception(f"[HIPPO] CRITICAL: ChromaDB initialization failed: {e}")
            raise

    def _startup_cleanup(self):
        """Phase 20: Mandatory environment sanitization on init."""
        logger.info("[HIPPO.CLEANUP] Performing environment sanitization...")
        try:
            # 1. Purge dirty/expired data
            now = time.time()
            ttl_days = int(os.getenv("CLAWBRAIN_TRACE_TTL_DAYS", 30))
            
            if ttl_days > 0:
                expiry_ts = now - (ttl_days * 86400)
                # Delete timestamp=0 (dirty) or expired records
                self.traces_col.delete(where={"$or": [{"timestamp": 0.0}, {"timestamp": {"$lt": expiry_ts}}]})
            else:
                # Only purge dirty data (timestamp=0)
                self.traces_col.delete(where={"timestamp": 0.0})
            
            # 2. Reclaim orphaned blobs (Placeholder)
            
            # 3. Transition aid: Clear legacy SQLite if exists
            db_path = self.db_dir / "hippocampus.db"
            if db_path.exists():
                try:
                    with sqlite3.connect(db_path) as conn:
                        conn.execute("DELETE FROM traces WHERE timestamp = 0.0")
                except: pass

        except Exception as e:
            logger.warning(f"[HIPPO.CLEANUP] Non-critical cleanup failure: {e}")

    # ── P18: Memory Capture & Persistence ───────────────────────────────────

    def save_trace(self, trace_id: str, payload: Dict[str, Any], search_text: str = None, session_id: str = "default", room_id: str = "general", threshold: int = None) -> None:
        """Store a lossless interaction trace with dynamic blob offloading."""
        now = time.time()
        raw_content = json.dumps(payload)
        checksum = hashlib.sha256(raw_content.encode()).hexdigest()
        
        # P10: Dynamic Offloading
        is_blob = False
        blob_path = ""
        limit = threshold or int(os.getenv("CLAWBRAIN_OFFLOAD_THRESHOLD_KB", 512)) * 1024
        
        if len(raw_content) > limit:
            is_blob = True
            rel_path = f"{trace_id}.json"
            full_path = self.blob_dir / rel_path
            full_path.write_text(raw_content)
            blob_path = str(rel_path)
            # Store only placeholder in DB to save memory
            raw_content = f"[OFFLOADED_BLOB:{rel_path}]"

        state = "ready"
        if payload and isinstance(payload, dict) and payload.get("reaction") is None:
            state = "pending"

        metadata = {
            "timestamp": now,
            "session_id": session_id,
            "room_id": room_id,
            "model": payload.get("model", ""),
            "trace_id": trace_id,
            "is_blob": 1 if is_blob else 0,
            "blob_path": blob_path,
            "checksum": checksum,
            "state": state,
            "raw_content": raw_content 
        }
        
        # P15/P18: High-fidelity retrieval uses search_text (human intent) as the document
        document = search_text if search_text else raw_content
        
        self.traces_col.upsert(
            ids=[trace_id],
            documents=[document],
            metadatas=[metadata]
        )

    def get_content(self, trace_id: str) -> Optional[str]:
        """Fetch the original raw content JSON."""
        res = self.traces_col.get(ids=[trace_id], include=["metadatas"])
        if not res or not res["ids"]: return None
        meta = res["metadatas"][0]
        
        # If it was offloaded, read from disk
        if meta.get("is_blob"):
            blob_path = self.blob_dir / meta.get("blob_path")
            if blob_path.exists():
                return blob_path.read_text()
            return None
            
        return meta.get("raw_content")

    def get_full_payload(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the complete original payload."""
        content_str = self.get_content(trace_id)
        if not content_str: return None
        try: return json.loads(content_str)
        except: return None

    def get_recent_traces(self, limit: int, session_id: str = "default") -> List[Dict[str, Any]]:
        """Fetch and sort recent traces."""
        # Note: if session_id is None, it should return all (legacy compat)
        where = {"session_id": session_id} if session_id else None
            
        res = self.traces_col.get(
            where=where,
            include=["metadatas", "documents"],
            limit=limit * 3
        )
        
        if not res or not res["ids"]: return []
            
        traces = []
        for i in range(len(res["ids"])):
            meta = res["metadatas"][i]
            traces.append({
                "trace_id": res["ids"][i],
                "timestamp": meta.get("timestamp") or 0,
                "model": meta.get("model"),
                "raw_content": meta.get("raw_content") or res["documents"][i],
                "session_id": meta.get("session_id"),
                "room_id": meta.get("room_id", "general")
            })
            
        traces.sort(key=lambda x: x["timestamp"], reverse=True)
        return traces[:limit]

    def get_all_session_ids(self) -> List[str]:
        """Return all unique session IDs found in traces."""
        # Use traces_col as the primary source for discovery
        res = self.traces_col.get(include=["metadatas"])
        if not res or not res["metadatas"]: return []
        sids = {meta.get("session_id") for meta in res["metadatas"] if meta.get("session_id")}
        return sorted(list(sids))

    def clear_wm_state(self, session_id: str) -> None:
        """Clear the WM snapshot."""
        self.wm_col.delete(where={"session_id": session_id})

    # ── P22: WorkingMemory Persistence ───────────────────────────────────────

    def save_wm_state(self, session_id: str, items: List[Any]) -> None:
        """Overwrite the active WM snapshot."""
        self.clear_wm_state(session_id)
        if not items: return
        
        ids, docs, metas = [], [], []
        for i, item in enumerate(items):
            uid = f"{session_id}_{item.trace_id}_{i}"
            ids.append(uid)
            docs.append(item.content)
            metas.append({
                "session_id": session_id,
                "trace_id": item.trace_id,
                "timestamp": item.timestamp,
                "activation": item.activation
            })
            
        self.wm_col.upsert(ids=ids, documents=docs, metadatas=metas)

    def load_wm_state(self, session_id: str) -> List[Dict[str, Any]]:
        """Restore the weighted WM snapshot."""
        res = self.wm_col.get(where={"session_id": session_id}, include=["metadatas", "documents"])
        if not res or not res["ids"]: return []
        
        items = []
        for i in range(len(res["ids"])):
            meta = res["metadatas"][i]
            items.append({
                "trace_id": meta["trace_id"],
                "content": res["documents"][i],
                "timestamp": meta["timestamp"],
                "activation": meta["activation"]
            })
        items.sort(key=lambda x: x["timestamp"])
        return items

    # ── Phase 50: Flattened Entity Registry (SSOT) ──────────────────────────

    def upsert_fact(self, session_id: str, entity: str, key: str, value: str, trace_id: str = None) -> str:
        """Update or insert a hard fact (Latest-Wins)."""
        fact_id = f"{session_id}_{entity}_{key}".replace(" ", "_")
        self.entities_col.upsert(
            ids=[fact_id],
            documents=[value],
            metadatas=[{
                "session_id": session_id,
                "entity": entity,
                "key": key,
                "timestamp": time.time(),
                "trace_id": trace_id or "manual"
            }]
        )
        return fact_id

    def get_facts_for_entities(self, session_id: str, entities: List[str]) -> List[Dict[str, Any]]:
        """Fetch registered attributes for a list of entities."""
        if not entities: return []
        res = self.entities_col.get(
            where={"$and": [{"session_id": session_id}, {"entity": {"$in": entities}}]}
        )
        facts = []
        if res and res["ids"]:
            for i in range(len(res["ids"])):
                meta = res["metadatas"][i]
                facts.append({
                    "entity": meta["entity"], "key": meta["key"],
                    "value": res["documents"][i], "timestamp": meta["timestamp"]
                })
        return facts

    def search(self, query: str, session_id: str = "default", room_id: str = None, limit: int = 5) -> List[str]:
        """Perform semantic retrieval from L2 Hippocampus."""
        where = {"session_id": session_id}
        if room_id:
            where = {"$and": [{"session_id": session_id}, {"room_id": room_id}]}
            
        res = self.traces_col.query(
            query_texts=[query],
            n_results=limit,
            where=where
        )
        return res["ids"][0] if res and res["ids"] else []

def clear_chroma_clients(): pass
