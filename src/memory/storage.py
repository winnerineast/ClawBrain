# Generated from design/memory_hippocampus.md v1.9 / GEMINI.md Rule 12
import sqlite3
import chromadb
import json
import time
import os
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger("GATEWAY.MEMORY")

_CHROMA_CLIENTS = {}

def get_chroma_client(db_path: Path):
    path_str = str(db_path)
    if path_str not in _CHROMA_CLIENTS:
        _CHROMA_CLIENTS[path_str] = chromadb.PersistentClient(path=path_str)
    return _CHROMA_CLIENTS[path_str]

def clear_chroma_clients():
    global _CHROMA_CLIENTS
    _CHROMA_CLIENTS.clear()

class Hippocampus:
    """
    ClawBrain Episodic Memory Engine (SSOT).
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
            self.traces_col = self.client.get_or_create_collection(name="traces", metadata={"hnsw:space": "cosine"})
            self.wm_col = self.client.get_or_create_collection(name="wm_state")
            self.entities_col = self.client.get_or_create_collection(name="entities")
            logger.info("[HIPPO] Storage stabilized (session_id unified).")
            self._startup_cleanup()
        except Exception as e:
            logger.exception(f"[HIPPO] Initialization failed: {e}")
            raise

    def _startup_cleanup(self):
        """Phase 20: Mandatory environment sanitization."""
        try:
            ttl_days = int(os.getenv("CLAWBRAIN_TRACE_TTL_DAYS", 30))
            if ttl_days > 0:
                expiry_ts = time.time() - (ttl_days * 86400)
                self.traces_col.delete(where={"$or": [{"timestamp": 0.0}, {"timestamp": {"$lt": expiry_ts}}]})
            else:
                self.traces_col.delete(where={"timestamp": 0.0})
            
            # Physical Orphan Cleanup
            all_traces = self.traces_col.get(include=["metadatas"])
            referenced_blobs = set()
            if all_traces and all_traces["metadatas"]:
                for meta in all_traces["metadatas"]:
                    if meta.get("is_blob") and meta.get("blob_path"):
                        referenced_blobs.add(os.path.basename(meta["blob_path"]))
            
            for file in self.blob_dir.glob("*.json"):
                if file.name not in referenced_blobs:
                    file.unlink()

            db_path = self.db_dir / "hippocampus.db"
            if db_path.exists():
                try:
                    with sqlite3.connect(db_path) as conn:
                        conn.execute("DELETE FROM traces WHERE timestamp = 0.0")
                except: pass

        except Exception as e:
            logger.warning(f"[HIPPO.CLEANUP] Sanitization skip: {e}")

    def save_trace(self, trace_id: str, payload: Dict[str, Any], search_text: str = None, session_id: str = "default", room_id: str = "general", threshold: int = None) -> Dict[str, Any]:
        """Store interaction trace."""
        raw_content = json.dumps(payload)
        limit = threshold or int(os.getenv("CLAWBRAIN_OFFLOAD_THRESHOLD_KB", 512)) * 1024
        
        is_blob = False
        blob_path = ""
        if len(raw_content) > limit:
            is_blob = True
            rel_path = f"{trace_id}.json"
            full_path = self.blob_dir / rel_path
            full_path.write_text(raw_content)
            blob_path = str(full_path.resolve())
            raw_content = f"[OFFLOADED_BLOB:{rel_path}]"

        metadata = {
            "timestamp": time.time(), "session_id": session_id, "room_id": room_id,
            "model": payload.get("model", ""), "trace_id": trace_id,
            "is_blob": is_blob, "blob_path": blob_path,
            "checksum": hashlib.sha256(json.dumps(payload).encode()).hexdigest(),
            "state": "ready" if payload.get("reaction") else "pending",
            "raw_content": raw_content 
        }
        
        # P15 Fix: If search_text is missing, extract user query from payload as document
        if not search_text:
            try:
                search_text = payload.get("stimulus", {}).get("messages", [{}])[-1].get("content", "")
            except: pass

        self.traces_col.upsert(ids=[trace_id], documents=[search_text or raw_content], metadatas=[metadata])
        return metadata

    def get_content(self, trace_id: str) -> Optional[str]:
        res = self.traces_col.get(ids=[trace_id], include=["metadatas"])
        if not res or not res["ids"]: return None
        meta = res["metadatas"][0]
        if meta.get("is_blob"):
            p = Path(meta.get("blob_path"))
            return p.read_text() if p.exists() else None
        return meta.get("raw_content")

    def get_full_payload(self, trace_id: str) -> Optional[Dict[str, Any]]:
        c = self.get_content(trace_id)
        try: return json.loads(c) if c else None
        except: return None

    def get_recent_traces(self, limit: int, session_id: str = None) -> List[Dict[str, Any]]:
        # P18: Default session_id is None to allow broad fetching in tests
        where = {"session_id": session_id} if session_id else None
        res = self.traces_col.get(where=where, include=["metadatas", "documents"], limit=limit * 3)
        if not res or not res["ids"]: return []
        traces = []
        for i in range(len(res["ids"])):
            m = res["metadatas"][i]
            traces.append({
                "trace_id": res["ids"][i], "timestamp": m.get("timestamp") or 0,
                "model": m.get("model"), "raw_content": res["documents"][i],
                "session_id": m.get("session_id"), "room_id": m.get("room_id", "general")
            })
        return sorted(traces, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def get_all_session_ids(self) -> List[str]:
        res = self.traces_col.get(include=["metadatas"])
        if not res or not res["metadatas"]: return []
        return sorted(list({m.get("session_id") for m in res["metadatas"] if m.get("session_id")}))

    def clear_wm_state(self, session_id: str):
        self.wm_col.delete(where={"session_id": session_id})

    def save_wm_state(self, session_id: str, items: List[Any]):
        self.clear_wm_state(session_id)
        if not items: return
        ids, docs, metas = [], [], []
        for i, it in enumerate(items):
            uid = f"{session_id}_{it.trace_id}_{i}"
            ids.append(uid); docs.append(it.content)
            metas.append({"session_id": session_id, "trace_id": it.trace_id, "timestamp": it.timestamp, "activation": it.activation})
        self.wm_col.upsert(ids=ids, documents=docs, metadatas=metas)

    def load_wm_state(self, session_id: str) -> List[Dict[str, Any]]:
        res = self.wm_col.get(where={"session_id": session_id}, include=["metadatas", "documents"])
        if not res or not res["ids"]: return []
        items = [{"trace_id": m["trace_id"], "content": d, "timestamp": m["timestamp"], "activation": m["activation"]} for d, m in zip(res["documents"], res["metadatas"])]
        return sorted(items, key=lambda x: x["timestamp"])

    def search(self, query: str, session_id: str = "default", room_id: str = None, limit: int = 10, include_distances: bool = False) -> Union[List[str], List[Dict[str, Any]]]:
        where = {"session_id": session_id}
        if room_id: where = {"$and": [{"session_id": session_id}, {"room_id": room_id}]}
        res = self.traces_col.query(query_texts=[query], n_results=limit, where=where)
        
        if not res or not res["ids"] or len(res["ids"]) == 0:
            return []
            
        ids = res["ids"][0]
        if include_distances:
            distances = res["distances"][0] if res.get("distances") else [0.0] * len(ids)
            return [{"id": tid, "distance": d} for tid, d in zip(ids, distances)]
        
        return ids

    def search_lexical(self, tokens: List[str], session_id: str = "default", limit: int = 10) -> List[str]:
        """v1.12: Substring-based retrieval to ensure technical facts (IDs, Ports) are captured."""
        results = set()
        
        # Path 1: ChromaDB $contains filter (efficient but strict)
        for token in tokens:
            if len(token) < 3: continue
            try:
                res = self.traces_col.get(
                    where={"session_id": session_id},
                    where_document={"$contains": token},
                    limit=limit
                )
                if res and res["ids"]:
                    results.update(res["ids"])
            except: pass
        
        # Path 2: Brute-force substring match on recent history (Fallback for precision)
        # If we still have room, scan the last 50 traces manually
        if len(results) < limit:
            recent = self.get_recent_traces(limit=50, session_id=session_id)
            for row in recent:
                content = str(row.get("raw_content", "")).upper()
                for t in tokens:
                    if t.upper() in content:
                        results.add(row["trace_id"])
                        break
                if len(results) >= limit: break
        
        return list(results)[:limit]

    def upsert_fact(self, session_id: str, entity: str, key: str, value: str, trace_id: str = None) -> str:
        fid = f"{session_id}_{entity}_{key}".replace(" ", "_")
        self.entities_col.upsert(ids=[fid], documents=[value], metadatas=[{"session_id": session_id, "entity": entity, "key": key, "timestamp": time.time(), "trace_id": trace_id or "manual"}])
        return fid

    def get_facts_for_entities(self, session_id: str, entities: List[str]) -> List[Dict[str, Any]]:
        if not entities: return []
        res = self.entities_col.get(where={"$and": [{"session_id": session_id}, {"entity": {"$in": entities}}]})
        return [{"entity": m["entity"], "key": m["key"], "value": d, "timestamp": m["timestamp"]} for d, m in zip(res["documents"], res["metadatas"])] if res else []
