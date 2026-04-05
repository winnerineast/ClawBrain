# design/memory_neocortex.md v1.2

## 1. Objective
Implement the **ClawBrain Neocortex** engine from scratch. This engine is responsible for asynchronously consolidating verbose episodic memories from the Hippocampus into refined semantic memories (knowledge summaries), while providing "visible semantic audit" capability.

## 2. Architecture

### 2.1 Data & Storage Model
- **Dependencies**: `db_dir` (to locate `hippocampus.db`), `ollama_url` (default `http://127.0.0.1:11434`).
- **Storage table (`neocortex_summaries`)**:
  - `context_id` (TEXT PRIMARY KEY)
  - `summary_text` (TEXT)
  - `last_updated` (REAL)
  - `hebbian_weight` (REAL DEFAULT 1.0)
- **Initialisation**: The SQLite table must be created automatically at instantiation time.

### 2.2 Semantic Distillation Engine
- **Method signature**: `async def distill(context_id: str, traces: List[Dict[str, Any]]) -> str`
- **Logic flow**:
  1. Iterate the `traces` list, extract all user and assistant dialogue content, and concatenate into a long text.
  2. Construct an instruction prompt: "Summarise the core technical decisions, user preferences, and resolved issues from the following conversation. Output as concise bullet points only."
  3. **Model selection**: Read the model name from env var `CLAWBRAIN_DISTILL_MODEL` (default `gemma4:e4b`).
  4. Call `ollama_url/api/generate` via `httpx.AsyncClient` with the merged prompt and selected model.
  5. Extract the `response` field and upsert it into the `neocortex_summaries` table.
  6. **Error handling**: On request failure, return a descriptive error string — do not raise a blocking exception.

### 2.3 Memory Recall Interface
- **Method signature**: `def get_summary(context_id: str) -> Optional[str]`
- Reads and returns the latest summary for the given session from SQLite.

## 3. Test Specification (High-Fidelity TDD)

All tests must be in `tests/test_p9_neocortex.py` with highly structured semantic comparison logs.

### 3.1 Core Fact Distillation Audit (Semantic Delta)
- **Test data**: Provide an interaction array containing 3 trivial exchanges and 1 core fact (e.g., `"Database version is 15.2"` or a similar unique parameter).
- **Audit requirements**:
  - **Precise assertion**: The test must not only check whether the summary is shorter, but also verify against a predefined set of "canary fact keywords" that no key fact is omitted.
  - **Log display**: Side-by-Side format — left column `EXPECTED EVIDENCE` lists required key facts; right column `ACTUAL EVIDENCE` shows confirmation markers (`[x]` or `[ ]`) for each fact in the summary.

## 4. Output Targets
1. `src/memory/neocortex.py`: Neocortex logic and storage.
2. `tests/test_p9_neocortex.py`: Robust semantic validation with high-fidelity output.
