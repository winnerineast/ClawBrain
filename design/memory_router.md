# design/memory_router.md v1.14 (Phase 56)

## 1. Objective
Implement the **ClawBrain MemoryRouter** — the central memory hub that orchestrates the three-layer memory system. It must provide an **Asynchronous Sequential Gate** to ensure that memory ingestion, distillation, and assembly for any given session occur in a consistent logical order without race conditions.

## 2. Architecture & Logic

### 2.1 Initialisation & Sub-module Mounting
- **Constructor parameters**: `db_dir` (default: dynamic), `distill_threshold` (default 50).
- **Sub-modules**: `Hippocampus`, `Neocortex`, `SignalDecomposer`, `VaultIndexer`.
- **Per-session Registry**:
  - `self._wm_sessions: Dict[str, WorkingMemory] = {}`
  - `self._session_locks: Dict[str, asyncio.Lock] = {}` — **Phase 32: Per-session concurrency control**.

### 2.2 Asynchronous Sequential Gate (ingest)
- **Method signature**: `async def ingest(payload, reaction=None, offload_threshold=None, session_id="default", sync_distill=False) -> str`
- **Logic (Phase 32)**:
  1. Acquire the lock for `session_id`: `async with self._get_session_lock(session_id):`.
  2. Generate `trace_id = uuid4()`.
  3. Extract `intent`.
  4. Call `hippo.save_trace(...)`.
  5. Call `_get_wm(session_id).add_item(...)`.
  6. **P22**: Persist WM snapshot.
  7. **Auto-distillation (awaited sequence)**:
     - Increment `_trace_counters[session_id]`.
     - If `_trace_counters[session_id] >= distill_threshold` OR `sync_distill` is True:
       - `await self._auto_distill_worker(session_id)` — **Crucial: Direct await ensures sequence completion before lock release.**
       - Reset `_trace_counters[session_id] = 0`.
  8. Return `trace_id`.

### 2.3 Automatic Distillation Worker
- **Method**: `async def _auto_distill_worker(session_id: str)`
- Internal method, now always called under a session lock.
- Fetches the most recent `distill_threshold` traces for `session_id`; passes them to `neo.distill(session_id, traces)`.

### 2.4 Combined Context Retrieval (get_combined_context)
- **Method signature**: `async def get_combined_context(session_id: str, query: str) -> str`
- **Logic (Phase 56)**:
  1. Acquire the lock for `session_id`: `async with self._get_session_lock(session_id):`. This ensures we don't read a summary or WM state while it is being updated by a parallel `ingest` or `distill` operation.
  2. Read `CLAWBRAIN_MAX_CONTEXT_CHARS` (default 2000).
  3. Perform L3 -> L1 -> Vault -> L2 greedy allocation (as defined in §2.6).

### 2.5 Dynamic Offload Threshold
- The `ingest` method accepts `offload_threshold` (bytes); if provided it overrides the Hippocampus default.
- **Verification**: Pass 1 MB data with `offload_threshold=500 KB`; verify offload triggers 100% of the time.

### 2.6 Greedy Context Budget (P15 + Phase 29/30/31 + Phase 56)
- **Background**: `get_combined_context` injected noisy strings and had sub-optimal layer priority.
- **Env var `CLAWBRAIN_MAX_CONTEXT_CHARS`**: Default `2000`.
- **Phase 29/30**: Neocortex silence and Plain-Text Hippocampus.
- **Phase 31/56 (Context Budgeting v2)**: Re-prioritise layers to L3 -> L1 -> Vault -> L2. 
- **Header Safety**: Before injecting a layer's content, the budget must be checked against the **header length plus a 20-character safety margin**. When appending content, the exact lengths of headers, newlines, and truncation ellipses (`...`) MUST be precisely deducted from the remaining character budget to prevent budget efficiency overruns (ISSUE-006).
- **Priority greedy allocation** (highest value density first):
  1. **L3 Neocortex summary first**: If exists, inject header `=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===` followed by the summary.
  2. **L1 Working Memory next**: Check if `remaining > 60` (header + safety). If so, inject header `=== ACTIVE CONVERSATION (WORKING MEMORY) ===` and then as much of the active messages as possible.
  3. **Ext Vault / Entities next**: If exists, inject header `=== EXTERNAL KNOWLEDGE (VAULT) ===` or `=== ENTITY REGISTRY ===` and append relevant facts.
  4. **L2 Hippocampus last**: Check if `remaining > 70` (header + safety). If so, inject header `=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===` and then append plain-text bullet points until budget exhausted.
- **Output Format**: Separate sections with a single newline. If no layers have content, return an empty string.
- **Log point**: \`[CTX_BUDGET] Budget: N | Used(L3): N | Used(L1): N | Used(V): N | Used(L2): N | Session: ctx\`.

### 2.7 Per-session Working Memory Isolation (P18)
- **Background**: A global `WorkingMemory` singleton shared across all sessions caused cross-session context contamination.
- **Fix**: Replace `self.wm: WorkingMemory` with `self._wm_sessions: Dict[str, WorkingMemory] = {}`; lazily create and cache per-session WM instances via `_get_wm(session_id)`.
- **`ingest` signature change**: Added `session_id: str = "default"` — routes to the correct WM instance and passes `session_id` to `hippo.save_trace`.
- **`_hydrate` change**: At startup, query `DISTINCT session_id` from `traces`; for each session, call `hippo.get_recent_traces(limit=15, session_id=session)` to restore the corresponding WM (fallback path — see §2.8).
- **`get_combined_context` change**: Calls `_get_wm(session_id).get_active_contents()` and `hippo.search(query, session_id=session_id)` to ensure full-path session isolation.

### 2.8 Exact Working Memory Persistence (P22)
- **Background**: `_hydrate` reconstructed WM from `traces`, losing exact `activation` values and original `timestamps` — attention state reset on every restart.
- **Fix**: Use `Hippocampus.save_wm_state / load_wm_state` to persist a WM snapshot after every `ingest`.
- **`ingest` change**: After `_get_wm(session_id).add_item(...)`, call `self.hippo.save_wm_state(session_id, wm.items)`.
- **`_hydrate` change**: First try `hippo.load_wm_state(session)` for an exact restore; fall back to the traces-rebuild path only if the snapshot is absent.
- **`clear_summary` coupling**: `DELETE /v1/memory/{session_id}` also calls `hippo.clear_wm_state(session_id)` and evicts the in-memory WM instance, ensuring the management API semantically clears all layers.

### 2.9 Hybrid Cognitive Retrieval (Phase 55 / v1.16)
- **Concept**: Combine vector similarity (intuition) with keyword matching (precision).
- **Multi-Path Retrieval**:
  1. **Semantic Path**: Top-20 vector search.
  2. **Lexical Path**: Top-20 keyword search (search items containing specific tokens from query).
  3. **Index Path**: Search recent entities and verified facts.
- **Fusion & Reranking**:
  - Merge all candidates, keeping unique items.
  - Scoring: `(Anchor Score * 150) + (Keyword Score * 30) + (Similarity * 10)`.
  - Result: Even if a fact has 0.9 distance (semantic failure), it is saved by its 100% keyword resonance.

## 4. Output Targets
- `src/memory/router.py`, `src/memory/storage.py`, `src/main.py`, `tests/test_p22_wm_persistence.py`.
