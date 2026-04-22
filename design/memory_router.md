# design/memory_router.md v1.21 (v0.2.1)

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
- **Header Safety**: Before injecting a layer's content, the budget must be checked against the **header length plus a 20-character safety margin**. Exact lengths of headers, newlines, and truncation ellipses MUST be precisely deducted.

### 2.5 Contextual Silence (v1.23)
- To prevent polluting the LLM prompt with empty headers, `get_combined_context` MUST return an empty string if NO long-term memory exists.
- **Long-term Gain Condition**: `any([thoughts, l3_summary, entity_facts, vault_results, l2_contents])`.
- Note: Working Memory (L1) presence alone does not satisfy the "gain" requirement for long-term retrieval, as L1 is expected to be part of the user's immediate message history anyway.

## 3. Core Sub-Systems (Retained from v1.x)

### 3.1 Dynamic Offload Threshold
- The `ingest` method accepts `offload_threshold` (bytes); if provided it overrides the Hippocampus default.
- High-volume payloads are automatically offloaded to the filesystem to keep ChromaDB performant.

### 3.2 Per-session Working Memory Isolation (P18)
- Memory is isolated via `self._wm_sessions: Dict[str, WorkingMemory] = {}`.
- **Strict Separation**: Cross-session context contamination is prevented by filtering all Hippo/Neocortex queries by `session_id`.

### 3.3 Exact Working Memory Persistence (P22)
- WM state is persisted after every `ingest` to ensure the attention state (activations/timestamps) survives system restarts.
- Reconstruction fallback: If a snapshot is missing, WM is rebuilt from the most recent interaction traces.

### 3.4 Hybrid Cognitive Retrieval (L2 Fallback Path)
- Combine vector similarity (intuition) with keyword matching (precision).
- Candidates are fused and reranked using: `(Anchor Score * 150) + (Subject Coverage * 60) + (Similarity * 15)`.
- This ensures technical facts (ports, IDs) are captured even when semantic distance is high.

## 4. Configuration & Resiliency
- **`CLAWBRAIN_HEARTBEAT_SECONDS`**: Interval for background processing.
- **`CLAWBRAIN_JUDGE_TIMEOUT`**: (Deprecated for read-only path, kept for manual triggers) Timeout for cognitive judge.
- **`CircuitBreaker`**: Protects the background heartbeat from LLM backend failures.

## 4. Output Targets
- `src/memory/router.py`: Heartbeat loop and read-only retrieval logic.
- `src/memory/neocortex.py`: Thought extraction.
- `tests/test_p50_thoughts.py`: Verification.
