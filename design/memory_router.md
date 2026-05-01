# design/memory_router.md v1.5 (Phase 61)

## 1. Objective
Implement the **ClawBrain MemoryRouter v2** — the central cognitive hub that orchestrates the "Breathing Brain" architecture. It must provide an **Asynchronous Sequential Gate** to ensure that memory ingestion, distillation, and assembly for any given session occur in a consistent logical order without race conditions, while decoupling background processing from real-time response generation.

## 2. Architecture & Logic

### 2.1 Initialisation & Sub-module Mounting
- **Constructor parameters**: `db_dir` (default: dynamic), `distill_threshold` (default 50).
- **Sub-modules**: `Hippocampus`, `Neocortex`, `SignalDecomposer`, `RoomDetector`, `VaultIndexer`.
- **Per-session Registry**:
  - `self._wm_sessions: Dict[str, WorkingMemory] = {}`
  - `self._session_locks: Dict[str, asyncio.Lock] = {}` — **Phase 32: Per-session concurrency control**.

### 2.2 Processing Logic

#### 2.2.1 Unified Significance Scoring
To handle wide and diverse datasets, the Router computes a `Significance Score` for every candidate:
- `Score = (Anchors * 150) + (Coverage * 80 * (1 + Similarity)) + (Similarity * 20)`

#### 2.2.2 Cognitive Admission (v1.4 - Judge-Centric)
Instead of hardcoded absolute gates, the system uses an adaptive "Wide Net" approach:
1. **Hard Anchors**: Any snippet containing a hard anchor (technical ID, proper noun) identified by the `SignalDecomposer` is admitted.
2. **Recall Focus**: The Pre-Filter is intentionally generous to ensure the LLM-based **Cognitive Judge** has a chance to evaluate potentially relevant context.
3. **Adaptive Thresholding**: Admission logic prioritizes `Subject Coverage` (lexical overlap) over `Similarity` (semantic vector distance) for technical recall.
4. **The Judge (Final Precision)**: The Neocortex Judge performs final semantic verification. If the Judge is reasoning-aware, the Pre-Filter prioritizes **Recall over Precision**.

### 2.3 Layered Retrieval Priority
Context is assembled in order of "Knowledge Density":
1. **L3 (Neocortex)**: Abstract summaries.
2. **L1 (Working Memory)**: Immediate conversation state.
3. **Entity Registry**: Verified facts and metadata extracted by `SignalDecomposer`.
4. **Vault**: External curated knowledge.
5. **L2 (Hippocampus)**: Historical episodic snippets.

### 2.4 Context Budgeting (P31 / Phase 55)
- **Env var `CLAWBRAIN_MAX_CONTEXT_CHARS`**: Default `2000`.
- **Header Safety**: Budget checked against the header length plus a 20-character safety margin.
- **Log point**: `[CTX_BUDGET] Budget: N | Used(L3): N | Used(L1): N | Used(L2): N | Session: ctx`.

### 2.5 The Breathing Brain (Heartbeat Loop)
- **Core Concept**: Cognitive background tasks are decoupled from real-time ingestion.
- **Priority Gating**:
  - **L1/L2 Storage**: MUST be synchronous (blocking) to ensure immediate retrieval in the next turn.
  - **Entity Mentions**: Extracted via fast regex in the request path and stored immediately in the registry to ensure Turn N+1 visibility.
  - **Verified Facts**: Deep mining via LLM is performed in the background heartbeat.
- **Method**: `async def _cognitive_heartbeat_loop()`
  - **Rhythm**: Orchestrated by `CLAWBRAIN_HEARTBEAT_SECONDS` (default: 30s).
  - **Task Queues**:
    - `_dirty_sessions: Set[str]`: Sessions requiring L3 distillation.
    - `_pending_trace_extractions: List[tuple[str, str]]`: Trace IDs for background Fact Evolution mining.

## 4. Output Targets
- `src/memory/router.py`, `src/memory/storage.py`, `src/main.py`, `tests/test_p22_wm_persistence.py`.
