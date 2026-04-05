# design/memory_hippocampus.md v1.8

## 1. Objective
Implement the **ClawBrain Hippocampus** storage engine from scratch. This engine handles lossless persistence of interaction traces, streaming offload of large payloads to disk, and full-text search via SQLite FTS5. It also enforces byte-level integrity audit. Core improvement: dynamic offload threshold based on model context window.

## 2. Architecture & Implementation Details

### 2.1 Storage Directory & Initialisation
- Default directory: `db_dir`, with a `blobs/` subdirectory for oversized files.
- Database file: `db_dir/hippocampus.db`.
- **SQLite table schema**:
  - `traces`: `trace_id` (TEXT PK), `timestamp` (REAL), `model` (TEXT), `is_blob` (INTEGER), `blob_path` (TEXT), `raw_content` (TEXT), `checksum` (TEXT), `context_id` (TEXT DEFAULT 'default').
  - `search_idx`: FTS5 virtual table with `trace_id` (UNINDEXED), `context_id` (UNINDEXED), and `content`.
  - `wm_state`: `session_id` (TEXT), `trace_id` (TEXT), `content` (TEXT), `activation` (REAL), `timestamp` (REAL), PRIMARY KEY `(session_id, trace_id)`.

### 2.2 Dynamic Tiered Storage (save_trace)
- **Method signature**: `save_trace(trace_id, payload, search_text="", threshold=None, context_id="default")`
- Serialise `payload` to JSON, compute byte length.
- **SHA-256 checksum (Bug 7 fix)**: Compute the SHA-256 hash of the raw UTF-8 bytes (hex string format).
- **Dynamic threshold**: If the caller provides `threshold` (in bytes), use it; otherwise fall back to 512 KB.
- **Timestamp (Bug 5 fix)**: Record the real wall-clock time via `time.time()` at insertion.
- **Offload logic**:
  - If `len > threshold`: write JSON to `blobs/{trace_id}.json`; set `is_blob=1`, `blob_path=<absolute path>`, `raw_content=""`.
  - If `len <= threshold`: set `is_blob=0`, `blob_path=""`, `raw_content=<JSON string>`.
- Store `checksum` and `context_id` in the `traces` row.
- If `search_text` is non-empty, insert into `search_idx`.
- **Return contract**: `{"trace_id": str, "is_blob": bool, "blob_path": str, "size": int, "checksum": str}`

### 2.3 Two-Level Full-Text Search (P15)
- **Background**: Exact-phrase matching (quoting the entire query) has very low recall against natural-language input.
- **Method signature**: `search(query: str, context_id: str = "default") -> List[str]`
- **Level 1 (exact phrase + session filter)**:
  `SELECT trace_id FROM search_idx WHERE content MATCH '"<full query>"' AND context_id = ?`
  Return immediately if results exist.
- **Level 2 (keyword AND + session filter)**:
  Split query on whitespace; discard tokens with length ≤ 2 or containing FTS5 special characters (`"*^()[]{}`); quote remaining tokens; join as `"word1" "word2" ...` (FTS5 AND semantics); limit to 5 tokens.
  `SELECT trace_id FROM search_idx WHERE content MATCH ? AND context_id = ?`
- Both levels catch `OperationalError` and return `[]` on failure.

### 2.4 Data Retrieval Interfaces
- **`get_content(trace_id: str) -> Optional[str]`**: If `is_blob`, read from the physical path; otherwise return `raw_content`.
- **`get_recent_traces(limit: int, context_id: str = None) -> List[Dict]`**: `SELECT * FROM traces ORDER BY timestamp DESC LIMIT ?`, optionally filtered by `WHERE context_id = ?`.
- **`get_all_session_ids() -> List[str]`**: `SELECT DISTINCT context_id FROM traces WHERE context_id IS NOT NULL` — used by `_hydrate`.

### 2.5 Session Isolation (P18)
- **Background**: Without a `context_id` column, cross-session queries contaminate each other.
- **Schema migration**: `ALTER TABLE traces ADD COLUMN context_id TEXT DEFAULT 'default'` (ignore `OperationalError` if already present). For `search_idx`, detect the missing column by probing with a `SELECT context_id`; if it raises `OperationalError`, drop and recreate the table.
- All read/write paths carry `context_id` — see §2.2 and §2.3.

### 2.6 TTL Auto-Cleanup & Dirty Data Purge (P20)
- **Background**: The early `timestamp=0.0` bug left large numbers of invalid records; long-running production DBs grow unbounded.
- **Cleanup strategy** (executed automatically at end of `_init_db`):
  1. **Dirty data**: `DELETE FROM traces WHERE timestamp = 0.0`; sync-delete matching `search_idx` rows.
  2. **TTL expiry**: Read `CLAWBRAIN_TRACE_TTL_DAYS` (default 30; `0` = disabled). `DELETE FROM traces WHERE timestamp > 0 AND timestamp < now - ttl_seconds`; sync-delete `search_idx` rows and blob files.
  3. **Orphan blob cleanup**: Scan `blobs/` for `.json` files with no corresponding `blob_path` in `traces`; delete them.
- **Log point**: After cleanup, emit `[HP_CLEAN] Purged dirty=N expired=N orphan_blobs=N`.

### 2.7 Working Memory Snapshot Persistence (P22)
- **Background**: `_hydrate` reconstructed WM from `traces`, losing exact `activation` values and original `timestamps`, causing attention state to reset on every restart.
- **Methods**:
  - `save_wm_state(session_id, items)`: `DELETE FROM wm_state WHERE session_id = ?` then `INSERT` all current WM items.
  - `load_wm_state(session_id) -> List[dict]`: Returns `(trace_id, content, activation, timestamp)` ordered by `timestamp ASC`.
  - `clear_wm_state(session_id)`: `DELETE FROM wm_state WHERE session_id = ?` (called by management API DELETE).

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
