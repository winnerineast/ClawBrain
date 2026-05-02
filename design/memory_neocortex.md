# design/memory_neocortex.md v1.2

## 1. Objective
Implement the **ClawBrain Neocortex** engine from scratch. This engine is responsible for asynchronously consolidating verbose episodic memories from the Hippocampus into refined semantic memories (knowledge summaries), while providing "visible semantic audit" capability.

## 2. Architecture

### 2.1 Data & Storage Model
- **Dependencies**: 
  - `db_dir`: Directory for SQLite storage.
  - `distill_url`: Base URL for the distillation provider (default: `http://127.0.0.1:11434` for Ollama or `http://127.0.0.1:8080/v1` for OpenAI-compatible local servers).
  - `distill_model`: Model name for distillation.
  - `distill_provider`: Protocol type (`ollama` or `openai-compatible`).
- **Storage table (`neocortex_summaries`)**:
  - `session_id` (TEXT PRIMARY KEY)
  - `summary_text` (TEXT)
  - `last_updated` (REAL)
  - `hebbian_weight` (REAL DEFAULT 1.0)

### 2.2 Semantic Distillation Engine
- **Method signature**: `async def distill(session_id: str, traces: List[Dict[str, Any]]) -> str`
- **Config priority**:
  1. URL: Env `CLAWBRAIN_DISTILL_URL` -> Constructor `distill_url`.
  2. Model: Env `CLAWBRAIN_DISTILL_MODEL` -> Constructor `distill_model`.
  3. API Key: Env `CLAWBRAIN_DISTILL_API_KEY` (optional).
  4. Provider: Env `CLAWBRAIN_DISTILL_PROVIDER` (default: `openai-compatible`).
- **Protocol Dispatch**:
  - **Ollama**: Call `distill_url/api/generate` with `prompt`. Extract `response`.
  - **OpenAI-compatible**: Call `distill_url/chat/completions` with `messages`. Extract `choices[0].message.content`.
- **Logic flow**:
  1. Iterate `traces` to build a conversation corpus.
  2. Construct the summarization prompt. The prompt MUST be template-based and strictly categorize extracted facts into 'Technical Decisions', 'User Preferences', and 'Project Context' to optimize for specific test dimensions (ISSUE-007).
  3. Dispatch to the selected provider.
  4. Upsert result into `neocortex_summaries`.
  5. **TasteGuard (Belief Anchor)**: Apply a protective layer over the distilled summary. Core, highly-weighted subjective facts (e.g., "The user hates ORMs") are anchored and highly resistant to being overwritten or unlearned by transient, contradictory data during future distillations.

### 2.4 Subjective Cognitive Judge (L6b Evaluator)
- **Background**: Replaces the objective "hallucination prevention" judge with a user-specific "Taste/Value Profile" judge.
- **Mechanism**: The judge must ask: "Does this context align with the user's specific architectural tastes and personal values?" rather than just checking for objective relevance.
- **Action**: Before context is finalized, an LLM call validates the assembled facts against the user's subjective TasteGuard profile.
- **Fail-open**: If the LLM throws an exception (e.g. timeout), the judge defaults to `True` (allowing the context).

### 2.5 Memory Recall Interface
- **Method signature**: `def get_summary(session_id: str) -> Optional[str]`
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
