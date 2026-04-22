# design/memory_router.md v1.20 (v0.2.0)

## 1. Objective
Implement the **ClawBrain MemoryRouter v2** — the central cognitive hub that orchestrates the "Breathing Brain" architecture. It decouples active memory processing (distillation, extraction) from real-time response generation (context assembly) to ensure ultra-low latency and grounded reasoning.

## 2. Architecture & Logic

### 2.1 The Breathing Brain (Heartbeat Loop)
- **Method**: `async def _cognitive_heartbeat_loop()`
- **Rhythm**: Autonomous background loop controlled by `CLAWBRAIN_HEARTBEAT_SECONDS` (default 30s).
- **Responsibilities**:
  1. **Entity Extraction**: Process `_pending_trace_extractions` queued by `ingest`.
  2. **Thought Distillation**: Execute `_auto_distill_worker` for any session in `_dirty_sessions`.
- **Decoupling**: `ingest` and `commit_turn` now only queue tasks and mark sessions as dirty. They no longer wait for LLM processing.

### 2.2 Foreground Reflex (get_combined_context)
- **Constraint**: **Strict Read-Only**. No synchronous LLM calls allowed.
- **Thought-Driven Retrieval Pipeline**:
  1. **Thought Search**: Query L3 `thoughts` collection for insights.
  2. **Root Evidence Resolution**: For each found thought, use its `source_traces` to fetch the raw interacton payloads from L2 Hippocampus.
  3. **Entity/Vault Search**: (Existing logic) Query verified facts and external knowledge.
  4. **L2 Fallback**: Only if Step 1 and 3 yield no high-level "gains", execute a standard vector/lexical search against raw traces.

### 2.3 Sequential Gate & Concurrency
- **Per-session Concurrency**: Maintain `self._session_locks: Dict[str, asyncio.Lock]`.
- All reads and writes to a session's state (WM, Thoughts, Traces) must be wrapped in `async with self._get_session_lock(session_id):`.

### 2.4 Greedy Context Budget (v2.0)
- **Priority Stack**: `Thoughts (L3)` -> `Evidence (L2 Source)` -> `Working Memory (L1)` -> `Entities` -> `Vault` -> `Fallback Snippets (L2)`.
- **Header Structure**:
  - `=== VERIFIED THOUGHTS (NEOCORTEX) ===`
  - `=== SUPPORTING EVIDENCE (ROOT SOURCES) ===`
  - `=== ACTIVE CONVERSATION (WORKING MEMORY) ===`

## 3. Configuration & Resiliency
- **`CLAWBRAIN_HEARTBEAT_SECONDS`**: Interval for background processing.
- **`CLAWBRAIN_JUDGE_TIMEOUT`**: (Deprecated for read-only path, kept for manual triggers) Timeout for cognitive judge.
- **`CircuitBreaker`**: Protects the background heartbeat from LLM backend failures.

## 4. Output Targets
- `src/memory/router.py`: Heartbeat loop and read-only retrieval logic.
- `src/memory/neocortex.py`: Thought extraction.
- `tests/test_p50_thoughts.py`: Verification.
