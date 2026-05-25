# Generated from design/memory_hippocampus.md v1.11 / GEMINI.md Rule 12
import sqlite3
import chromadb
from chromadb.config import Settings
import json
import time
import os
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from src.utils.config import get_env

logger = logging.getLogger("GATEWAY.MEMORY")

class ChromaEmbedWrapper(chromadb.api.types.EmbeddingFunction):
    """v1.11: Wrapper for LLMClient.EmbedClient to satisfy ChromaDB's sync interface."""
    def __init__(self, embed_client):
        self.embed_client = embed_client
        self._count = 0

    def __call__(self, input: chromadb.api.types.Documents) -> chromadb.api.types.Embeddings:
        if not self.embed_client:
            return [] # Fallback to Chroma default if none provided
        
        self._count += 1
        start = time.time()
        # Progress Indicator for Regression Monitoring
        sample = input[0][:30].replace("\n", " ") if input else "Empty"
        print(f"  [EMBED-LOG] Task #{self._count}: Encoding {len(input)} documents... (Sample: '{sample}')", end="\r", flush=True)
        
        res = self.embed_client.embed_sync(input)
        
        elapsed = time.time() - start
        if elapsed > 1.0: # Only log slow embeddings
             print(f"  [EMBED-LOG] Task #{self._count}: Completed in {elapsed:.2f}s{' '*20}", flush=True)
             
        return res
    
    def name(self) -> str:
        return f"clawbrain_{self.embed_client.model if self.embed_client else 'default'}"

_CHROMA_CLIENTS = {}

def get_chroma_client(db_path: Path):
    path_str = str(db_path)
    if path_str not in _CHROMA_CLIENTS:
        _CHROMA_CLIENTS[path_str] = chromadb.PersistentClient(
            path=path_str,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
    return _CHROMA_CLIENTS[path_str]

def clear_chroma_clients():
    global _CHROMA_CLIENTS
    _CHROMA_CLIENTS.clear()

class Hippocampus:
    """
    ClawBrain Episodic Memory Engine (SSOT).
    Rule 12: Unified session_id terminology enforced.
    """
    def __init__(self, db_dir: str, embed_client = None):
        self.db_dir = Path(db_dir)
        self.chroma_path = self.db_dir / "chroma"
        self.blob_dir = self.db_dir / "blobs"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        
        self.embed_fn = ChromaEmbedWrapper(embed_client) if embed_client else None

        try:
            self.client = get_chroma_client(self.chroma_path)
            
            # Helper to safely get or recreate collection on embedding conflict
            def get_safe_col(name, metadata=None):
                try:
                    return self.client.get_or_create_collection(
                        name=name,
                        metadata=metadata,
                        embedding_function=self.embed_fn
                    )
                except ValueError as e:
                    if "embedding function conflict" in str(e).lower():
                        logger.warning(f"[HIPPO] Embedding conflict for {name}. Rebuilding collection to match new model.")
                        self.client.delete_collection(name)
                        return self.client.get_or_create_collection(
                            name=name,
                            metadata=metadata,
                            embedding_function=self.embed_fn
                        )
                    raise

            self.traces_col = get_safe_col("traces", metadata={"hnsw:space": "cosine"})
            self.wm_col = get_safe_col("wm_state")
            self.entities_col = get_safe_col("entities")

            logger.info("[HIPPO] Storage stabilized (session_id unified).")
            self._startup_cleanup()
        except Exception as e:
            logger.exception(f"[HIPPO] Initialization failed: {e}")
            raise

    def _startup_cleanup(self):
        """Phase 20: Mandatory environment sanitization."""
        try:
            ttl_days = int(get_env("CLAWBRAIN_TRACE_TTL_DAYS", 30))
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
        limit = threshold or int(get_env("CLAWBRAIN_OFFLOAD_THRESHOLD_KB", 512)) * 1024
        
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
            # Use raw_content from metadata if available, otherwise fallback to document
            content = m.get("raw_content") or res["documents"][i]
            traces.append({
                "trace_id": res["ids"][i], "timestamp": m.get("timestamp") or 0,
                "model": m.get("model"), "raw_content": content,
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
        try:
            res = self.traces_col.query(query_texts=[query], n_results=limit, where=where)
        except Exception as e:
            # Phase 65: Graceful fallback for desynchronized HNSW index
            if "Error finding id" in str(e) or "Internal error" in str(e):
                logger.warning(f"[HIPPO.SEARCH] ChromaDB index lag detected. Falling back to metadata scan for session {session_id}")
                res = self.traces_col.get(where=where, limit=limit, include=["metadatas", "documents"])
                if not res or not res["ids"]: return []
                ids = res["ids"]
                if include_distances:
                    return [{"id": tid, "distance": 0.5} for tid in ids]
                return ids
            raise
        
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
        if len(results) < limit:
            recent = self.get_recent_traces(limit=100, session_id=session_id)
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
        self.entities_col.upsert(
            ids=[fid], 
            documents=[value], 
            metadatas=[{"session_id": session_id, "entity": entity, "key": key, "timestamp": time.time(), "trace_id": trace_id or "manual"}]
        )
        return fid

    def get_facts_for_entities(self, session_id: str, entities: List[str]) -> List[Dict[str, Any]]:
        if not entities: return []
        res = self.entities_col.get(where={"$and": [{"session_id": session_id}, {"entity": {"$in": entities}}]})
        return [{"entity": m["entity"], "key": m["key"], "value": d, "timestamp": m["timestamp"]} for d, m in zip(res["documents"], res["metadatas"])] if res else []
