# design/memory_hippocampus.md v1.9

## 1. Objective
Implement the **ClawBrain Hippocampus** storage engine using **ChromaDB**. This engine handles lossless persistence of interaction traces, streaming offload of large payloads to disk, and **semantic vector search** via an embedded ChromaDB instance. It also enforces byte-level integrity audit and session-isolated retrieval.

## 2. Architecture & Implementation Details

### 2.1 Storage Directory & Initialisation
- Default directory: `db_dir`, with a `blobs/` subdirectory for oversized files.
- **ChromaDB persistence**: `db_dir/chroma/`.
- **Collections**:
  - `traces`: Stores episodic archive. Documents are the `search_text` (intent) or `raw_content`. Metadata includes `timestamp`, `model`, `is_blob`, `blob_path`, `checksum`, and `session_id`.
  - `wm_state`: Stores L1 working memory snapshot persistence.

### 2.2 Dynamic Tiered Storage (save_trace)
- **Method signature**: `save_trace(trace_id, payload, search_text="", threshold=None, session_id="default")`
- Serialise `payload` to JSON, compute byte length.
- **SHA-256 checksum**: Compute the SHA-256 hash of the raw UTF-8 bytes.
- **Offload logic**:
  - If `len > threshold`: write JSON to `blobs/{trace_id}.json`; set `is_blob=1`.
  - If `len <= threshold`: set `is_blob=0`.
- **ChromaDB Insert**: `traces_col.add(ids=[trace_id], documents=[search_text or raw_content], metadatas=[{...}])`.

### 2.3 Semantic Vector Search (Phase 33 / v1.11 Update)
- **Background**: Replaces legacy SQLite FTS5 with semantic recall.
- **Method signature**: `search(query: str, session_id: str = "default", limit: int = 10, include_distances: bool = False) -> Union[List[str], List[Dict[str, Any]]]`
- **Implementation**:
  `traces_col.query(query_texts=[query], n_results=limit, where={"session_id": session_id})`

### 2.8 Hybrid Retrieval Support (v1.11)
- **Lexical Search**: `search_lexical(tokens: List[str], session_id: str, limit: int = 10) -> List[str]`
- **Implementation**: Uses ChromaDB's `where_document` filter with `$contains` or local iterative scanning of the `raw_content` index to ensure exact keyword matches (IDs, Ports, Tokens) are not lost by the vector model.
- **Result**: Router will perform a Union of Semantic and Lexical paths.

### 2.4 Data Retrieval Interfaces
- **`get_content(trace_id: str) -> Optional[str]`**: Retrieve from ChromaDB document or blob file.
- **`get_recent_traces(limit: int, session_id: str = None) -> List[Dict]`**: Retrieve from ChromaDB, filtered by `session_id`, and sorted by `timestamp` in Python.
- **`get_all_session_ids() -> List[str]`**: Scans ChromaDB metadatas for unique `session_id` values.

### 2.5 Session Isolation (P18)
- Strict isolation enforced via ChromaDB's `where={"session_id": session_id}` filter on all query/get operations.

### 2.6 TTL Auto-Cleanup & Dirty Data Purge (P20)
- **Cleanup strategy**:
  1. **Dirty data**: `traces_col.delete(where={"timestamp": 0.0})`.
  2. **TTL expiry**: `traces_col.delete(where={"timestamp": {"$lt": cutoff}})`. Sync-delete blob files.
  3. **Orphan blob cleanup**: Scan `blobs/` for files not referenced in ChromaDB metadata.

### 2.7 Working Memory Snapshot Persistence (P22)
- **Collection**: `wm_state`.
- **Methods**: `save_wm_state`, `load_wm_state`, `clear_wm_state`.
- Items are sorted by `timestamp` in Python after retrieval.

## 3. Test Specification (High-Fidelity TDD)

All tests must be in `tests/test_p7_hippocampus.py` with Side-by-Side audit output.

### 3.1 Byte-Level Integrity Audit
- Generate a payload exceeding `threshold` and call `save_trace`.
- Read back the physical blob file and compute its SHA-256.
- **Log display**: Side-by-Side showing both SHA-256 values — they must be visually identical.

### 3.2 Search Precision Audit
- Insert a canary fact containing special characters (e.g., `SILVER-FOX-42`) alongside several noise entries.
- Call `search("SILVER-FOX-42")`.
- **Log display**: Side-by-Side showing EXPECTED `trace_id` vs ACTUAL returned ID list (not just True/False).

## 4. Output Targets
1. `src/memory/storage.py`: SQLite interaction implementing all logic above.
2. `tests/test_p7_hippocampus.py`: Robust validation with high-fidelity output.
