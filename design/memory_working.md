# design/memory_working.md v1.4

## 1. Objective
Implement the **ClawBrain WorkingMemory** from scratch. This must implement a dual-factor dynamics model for message residency, and fully disclose the computation formula and score sources in audit logs — ensuring the focus and decay logic is 100% auditable.

## 2. Specifications

### 2.1 Data Structures
- **WorkingMemoryItem**: Contains `trace_id`, `content`, `timestamp`, and real-time `activation`.
- **Manager constraints**:
  - `MAX_CAPACITY`: Hard limit of 15 items.
  - `THRESHOLD`: Eviction cutoff at activation 0.3.
  - `DECAY_LAMBDA`: Time decay constant 0.001.

### 2.2 Dual-Factor Mathematical Model
Each item's activation $A$ is computed as:

$$A = \text{TimeScore} + \text{RelevanceScore}$$

1. **TimeScore** (max 0.7): $0.7 \times \exp(-0.001 \times \Delta t)$
2. **RelevanceScore** (max 0.3): $0.3 \times (\text{Common\_Words} / \text{Current\_Input\_Words})$

### 2.3 Dynamic Cleanup Logic
After every `add_item` call:
1. **Refresh**: Recompute activation for every item in memory.
2. **Threshold eviction**: Remove items where $A < 0.3$.
3. **Capacity eviction**: If count > 15, sort by $A$ descending and keep the top 15.

### 2.4 Persistence (P22)
- **Background**: WorkingMemory is purely in-memory. `_hydrate` reconstructed WM from Hippocampus traces, losing exact `activation` values and original `timestamps` — attention state reset on every restart.
- **Solution**: Add a `wm_state` table to `hippocampus.db`; persist a snapshot after every `ingest`.
- **Schema**: `wm_state(session_id TEXT, trace_id TEXT, content TEXT, activation REAL, timestamp REAL, PRIMARY KEY (session_id, trace_id))`
- **Write timing**: After `_get_wm(ctx).add_item(...)` in `MemoryRouter.ingest()`, call `hippo.save_wm_state(context_id, wm.items)` — overwrites the full snapshot for that session (DELETE then INSERT).
- **Read timing**: `_hydrate()` first calls `hippo.load_wm_state(session)` for an exact restore (preserves `activation` + `timestamp`); falls back to the old traces-rebuild path only if no snapshot exists.
- **Cleanup coupling**: `DELETE /v1/memory/{session_id}` also clears the corresponding `wm_state` rows; TTL cleanup clears expired sessions' `wm_state` as well.
- **New `Hippocampus` methods**:
  - `save_wm_state(session_id, items: List[WorkingMemoryItem])`
  - `load_wm_state(session_id) -> List[dict]` (fields: trace_id, content, activation, timestamp)
  - `clear_wm_state(session_id)`

## 3. Test Specification (High-Fidelity TDD)

Test scripts must output **"with full derivation trace"** Side-by-Side logs.

### 3.1 Time Decay Full Record
- **Requirement**: Print $\Delta t$ and its intermediate value after substitution.
- **Log example**: `T_diff: 1000s | Calc: 0.7 * exp(-0.001*1000) = 0.2575`

### 3.2 Topic Activation Breakdown
- **Requirement**: Show detailed keyword-match evidence.
- **Log example**: `Match: {'database'} | Count: 1 | Focus_Len: 5 | Rel_Score: 0.3 * (1/5) = 0.06`

### 3.3 State Comparison Display (Rule 8)
- After every request round, display the list of remaining item IDs in Working Memory and their corresponding activation values.

## 4. Output Targets
1. `src/memory/working.py`: Working memory logic with derivation-trace support.
2. `src/memory/storage.py`: `wm_state` table and save/load/clear methods.
3. `src/memory/router.py`: `ingest()` writes snapshot; `_hydrate()` restores from snapshot first.
4. `src/main.py`: `DELETE /v1/memory/{session_id}` calls `clear_wm_state`.
5. `tests/test_p22_wm_persistence.py`: Verify exact activation restore and cross-restart consistency.
