# Generated from design/memory_vault.md v1.0
import os
import json
import hashlib
import time
import logging
from pathlib import Path
from typing import Dict, Any, List
import chromadb
from src.memory.storage import get_chroma_client

logger = logging.getLogger("GATEWAY.MEMORY.VAULT")

class VaultIndexer:
    """
    Incremental Vault Indexer with mtime + hash change detection.
    Runs in the Cognitive Plane to sync local markdown files to ChromaDB.
    """
    
    def __init__(self, vault_path: str, db_dir: Path, client: chromadb.PersistentClient):
        self.vault_path = Path(vault_path)
        self.db_dir = db_dir
        self.client = client
        self.state_file = self.db_dir / "vault_state.json"
        
        # Collection for vault knowledge
        self.collection = self.client.get_or_create_collection(
            name="vault_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except:
                return {"files": {}}
        return {"processed_files": {}}

    def _save_state(self):
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def _get_file_hash(self, path: Path) -> str:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    async def scan(self) -> Dict[str, int]:
        """
        Performs a full incremental scan of the vault.
        Returns a summary of actions taken.
        """
        if not self.vault_path.exists():
            logger.warning(f"[VAULT] Path not found: {self.vault_path}")
            return {"scanned": 0, "indexed": 0, "skipped": 0}

        stats = {"scanned": 0, "indexed": 0, "skipped": 0, "hash_checked": 0}
        processed_files = self.state.get("processed_files", {})
        new_processed = {}

        # 1. Walk and Detect Changes
        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if not file.endswith(".md"):
                    continue
                
                stats["scanned"] += 1
                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(self.vault_path))
                
                mtime = os.path.getmtime(full_path)
                old_meta = processed_files.get(rel_path, {})
                
                # Rule 3.1: TC_STALE check
                if old_meta and old_meta.get("mtime") == mtime:
                    stats["skipped"] += 1
                    new_processed[rel_path] = old_meta
                    continue
                
                # mtime changed, Rule 3.1: TC_TOUCH check (Hash verification)
                stats["hash_checked"] += 1
                current_hash = self._get_file_hash(full_path)
                
                if old_meta and old_meta.get("hash") == current_hash:
                    # Content identical despite mtime change (e.g. 'touch')
                    stats["skipped"] += 1
                    new_processed[rel_path] = {"mtime": mtime, "hash": current_hash}
                    logger.info(f"[VAULT] Skip (Hash Match): {rel_path}")
                    continue
                
                # Real change detected (TC_REAL or TC_ZERO)
                logger.info(f"[VAULT] Indexing: {rel_path}")
                try:
                    await self._index_file(full_path, rel_path)
                    new_processed[rel_path] = {"mtime": mtime, "hash": current_hash}
                    stats["indexed"] += 1
                except Exception as e:
                    logger.error(f"[VAULT] Failed to index {rel_path}: {e}")

        # 2. Cleanup deletions
        current_rel_paths = set(new_processed.keys())
        for old_rel in list(processed_files.keys()):
            if old_rel not in current_rel_paths:
                logger.info(f"[VAULT] Removing deleted file: {old_rel}")
                self.collection.delete(where={"file_path": old_rel})

        self.state["processed_files"] = new_processed
        self._save_state()
        return stats

    async def _index_file(self, full_path: Path, rel_path: str):
        """Chunks and embeds a single markdown file."""
        content = full_path.read_text(encoding="utf-8")
        
        # Remove old entries for this file
        self.collection.delete(where={"file_path": rel_path})
        
        # Simple Chunking (Fixed size 1000 chars for v1.0)
        chunks = []
        size = 1000
        overlap = 100
        
        for i in range(0, len(content), size - overlap):
            chunk = content[i : i + size]
            chunks.append(chunk)
            if i + size >= len(content):
                break
        
        ids = [f"vault_{rel_path}_{j}" for j in range(len(chunks))]
        metadatas = [{"file_path": rel_path, "chunk_index": j} for j in range(len(chunks))]
        
        if ids:
            self.collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadatas
            )
