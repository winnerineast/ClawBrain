# design/memory_neocortex.md v2.1 (v0.2.1 - Thought-Retriever)

## 1. Objective
Implement the **ClawBrain Neocortex v2.1** — a high-level cognitive processor that transforms verbose episodic interactions (L2) into granular, grounded "Thoughts" (L3). It employs **Root Source Mapping** to ensure every insight is traceable to its original interaction, and a **Cognitive Judge** to ensure retrieval precision.

## 2. Architecture

### 2.1 Thought Data Model
- **Storage**: ChromaDB `thoughts` collection (Vector search enabled).
- **Thought Schema (JSON)**:
  - `thought`: The distilled insight or fact (TEXT).
  - `source_traces`: List of trace IDs supporting this thought (LIST[TEXT]).
  - `confidence`: Confidence score (0.0 to 1.0).
  - `metadata`: `session_id`, `timestamp`.

### 2.2 Thought Distillation Engine (v2.0)
- **Method signature**: `async def distill(session_id: str, traces: List[Dict[str, Any]]) -> str`
- **Rhythm**: Triggered by the **Breathing Brain** heartbeat loop (Background).
- **Logic flow**:
  1. Iterate `traces` and prefix messages with their `[trace_id]`.
  2. Prompt LLM to extract granular insights in **JSON format**.
  3. **Strict Requirement**: Every thought MUST include the `source_traces` list containing the relevant trace IDs from the prompt.
  4. Upsert individual thoughts into ChromaDB `thoughts` collection.

### 2.3 Grounded Recall & Cognitive Judge (v2.1)
- **Method signature**: `search_thoughts(query: str, session_id: str) -> List[Dict]`
- Returns thoughts matching the query, including their `source_traces`.
- **Cognitive Judge (`verify_relevance`)**:
  - **Goal**: Prevent retrieval of semantically similar but logically irrelevant "hallucinated" context.
  - **Implementation**: Uses a fast LLM to verify if a retrieved snippet or thought specifically answers the user query.
  - **Verdict**: Returns "YES" or "NO". Router uses this to gate inclusion in the final context.

## 3. Test Specification (v2.0)
- **Root Mapping Audit**: Verify that for a given "Thought", the resolved "Evidence" contains the actual keywords from the original interaction.
- **Deduplication Audit**: (v0.3) Verify that similar thoughts are merged rather than duplicated.

## 4. Output Targets
1. `src/memory/neocortex.py`: Thought extraction and JSON parsing logic.
2. `src/memory/storage.py`: `thoughts_col` and Root Source Resolution methods.
3. `tests/test_p50_thoughts.py`: Lifecycle verification.
