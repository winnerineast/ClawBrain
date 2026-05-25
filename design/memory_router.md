# design/memory_router.md v1.20

## 1. Objective
Implement the **ClawBrain MemoryRouter v2** — the central cognitive hub that orchestrates the "Breathing Brain" architecture. It must provide an **Asynchronous Sequential Gate** to ensure that memory ingestion, distillation, and assembly for any given session occur in a consistent logical order without race conditions, while decoupling background processing from real-time response generation. **v1.20: Implementation of topic-aware semantic retrieval filtering for strict room-based isolation.**

## 2. Architecture & Logic

### 2.1 Initialisation & Sub-module Mounting
- **Constructor parameters**: `db_dir` (default: dynamic), `distill_threshold` (default 50).
- **Intelligent Resource Management**:
  - **LLMScheduler**: Discovers and benchmarks local/cloud LLMs for specialized tasks.
  - **Discovery**: Automatically selects the best `embedding` and `chat` models during initialization.
- **CircuitBreaker**: Prevents cascading failures. Separate breakers for `room_detection`, `distillation`, and `heartbeat`.
- **Sub-modules**: `Hippocampus`, `Neocortex`, `SignalDecomposer`, `RoomDetector`, `VaultIndexer`, `PageIndexer`.
- **Per-session Registry**:
  - `self._wm_sessions: Dict[str, WorkingMemory] = {}`
  - `self._session_locks: Dict[str, asyncio.Lock] = {}` — **Phase 32: Per-session concurrency control**.

### 2.2 Processing Logic

#### 2.2.1 Unified Significance Scoring & Topic-Aware Isolation
To handle wide and diverse datasets, the Router computes a `Significance Score` for every candidate:
- `Score = (Anchors * 150) + (Coverage * 80 * (1 + Similarity)) + (Similarity * 20)`
- **Topic-Aware Retrieval**: The semantic search in `get_combined_context()` must isolate episodic memory by the active room ID of the current session (`self._get_current_room(session_id)`) rather than querying a hardcoded `"general"` room. This guarantees strict privacy and prioritized recall.

#### 2.2.2 Hybrid Retrieval Strategy (PageIndex Integration)
The Router orchestrates a two-tier retrieval process:
1.  **Vector Path (VaultIndexer)**: Default for all documents. Provides candidate snippets via semantic similarity.
2.  **Reasoning Path (PageIndexer)**: Supplements the Vector path for complex technical recall.
    - **Trigger Heuristic**:
        - `If Vector Confidence < 0.7 AND Document Size > 5000 chars`
        - OR `If Query contains deep reasoning keywords (e.g., "compare", "parameter", "manual")`.
    - **Execution**: Invokes `PageIndexer.reasoning_search(query)` to traverse the TOC tree and find precise leaf nodes.

#### 2.2.3 Cognitive Admission (v1.4 - Judge-Centric)
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
- **CognitiveWorker**: An internal queue-based worker that executes asynchronous tasks (`topic_detection`, `distill`, `vault_scan`, `build_tree`) to prevent blocking the main heartbeat.
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
