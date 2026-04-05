# design/memory_router.md v1.11

## 1. Objective
Implement the **ClawBrain MemoryRouter** — the central memory hub that orchestrates the three-layer memory system. It must correctly connect Working Memory (L1), Hippocampus (L2), and Neocortex (L3), and provide a unified `ingest / get_combined_context` interface to the gateway.

## 2. Architecture & Logic

### 2.1 Initialisation & Sub-module Mounting
- **Constructor parameters**: `db_dir` (default `/home/nvidia/ClawBrain/data`), `distill_threshold` (default 50).
- **Sub-modules**: `Hippocampus(db_dir)`, `Neocortex(db_dir)`, `SignalDecomposer()`.
- **Per-session WM registry**: `self._wm_sessions: Dict[str, WorkingMemory] = {}` — see §2.7.

### 2.2 Signal Ingestion (ingest)
- **Method signature**: `async def ingest(payload, reaction=None, offload_threshold=None, context_id="default") -> str`
- Logic:
  1. Generate `trace_id = uuid4()`.
  2. Extract `intent = decomposer.extract_core_intent(payload)`.
  3. Call `hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, search_text=intent, threshold=offload_threshold, context_id=context_id)`.
  4. Call `_get_wm(context_id).add_item(trace_id, intent)`.
  5. **P22**: Persist WM snapshot via `hippo.save_wm_state(context_id, wm.items)`.
  6. Increment `_trace_counter`; if it reaches `distill_threshold`, spawn `_auto_distill_worker(context_id)` as an async task and reset counter.

### 2.3 Automatic Distillation Worker
- **Method**: `async def _auto_distill_worker(context_id: str)`
- Uses `asyncio.Lock` to prevent concurrent distillations.
- Fetches the most recent `distill_threshold` traces for `context_id`; deserialises and passes them to `neo.distill(context_id, traces)`.

### 2.4 Combined Context Retrieval (get_combined_context)
- **Method signature**: `async def get_combined_context(context_id: str, current_focus: str) -> str`
- Reads `CLAWBRAIN_MAX_CONTEXT_CHARS` (default 2000) as total budget.

### 2.5 Dynamic Offload Threshold
- The `ingest` method accepts `offload_threshold` (bytes); if provided it overrides the Hippocampus default.
- **Verification**: Pass 1 MB data with `offload_threshold=500 KB`; verify offload triggers 100% of the time.

### 2.6 Greedy Context Budget (P15)
- **Background**: `get_combined_context` had no upper bound; after long-running sessions it could overflow the model context window.
- **Env var `CLAWBRAIN_MAX_CONTEXT_CHARS`**: Default `2000`; controls the total character limit of memory injected per request.
- **Priority greedy allocation** (highest value density first, no fixed ratios):
  1. **L3 Neocortex summary first**: Inject the full summary; truncate with `...` if it exceeds the remaining budget.
  2. **L2 Hippocampus next**: Use remaining budget to append recalled snippets in retrieval order; stop when the next snippet would exceed what remains.
  3. **L1 Working Memory last**: Use remaining budget to inject active messages; truncate if needed.
- **Log point**: `[CTX_BUDGET] Budget: N | Used(L3): N | Used(L2): N | Used(L1): N | Session: ctx`.

### 2.7 Per-session Working Memory Isolation (P18)
- **Background**: A global `WorkingMemory` singleton shared across all sessions caused cross-session context contamination.
- **Fix**: Replace `self.wm: WorkingMemory` with `self._wm_sessions: Dict[str, WorkingMemory] = {}`; lazily create and cache per-session WM instances via `_get_wm(context_id)`.
- **`ingest` signature change**: Added `context_id: str = "default"` — routes to the correct WM instance and passes `context_id` to `hippo.save_trace`.
- **`_hydrate` change**: At startup, query `DISTINCT context_id` from `traces`; for each session, call `hippo.get_recent_traces(limit=15, context_id=session)` to restore the corresponding WM (fallback path — see §2.8).
- **`get_combined_context` change**: Calls `_get_wm(context_id).get_active_contents()` and `hippo.search(query, context_id=context_id)` to ensure full-path session isolation.

### 2.8 Exact Working Memory Persistence (P22)
- **Background**: `_hydrate` reconstructed WM from `traces`, losing exact `activation` values and original `timestamps` — attention state reset on every restart.
- **Fix**: Use `Hippocampus.save_wm_state / load_wm_state` to persist a WM snapshot after every `ingest`.
- **`ingest` change**: After `_get_wm(context_id).add_item(...)`, call `self.hippo.save_wm_state(context_id, wm.items)`.
- **`_hydrate` change**: First try `hippo.load_wm_state(session)` for an exact restore; fall back to the traces-rebuild path only if the snapshot is absent.
- **`clear_summary` coupling**: `DELETE /v1/memory/{session_id}` also calls `hippo.clear_wm_state(session_id)` and evicts the in-memory WM instance, ensuring the management API semantically clears all layers.

## 4. Output Targets
- `src/memory/router.py`, `src/memory/storage.py`, `src/main.py`, `tests/test_p22_wm_persistence.py`.
