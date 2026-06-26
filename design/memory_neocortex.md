# design/memory_neocortex.md v1.5

## 1. Objective
Implement the **ClawBrain Neocortex** engine from scratch. This engine is responsible for asynchronously consolidating verbose episodic memories from the Hippocampus into refined semantic memories (knowledge summaries), while providing "visible semantic audit" capability. **v1.4: Refactored to use ChromaDB for persistent summaries and LLMFactory for provider-agnostic distillation.** **v1.5: Expose the distill_url attribute to maintain compatibility with test suites.**

## 2. Architecture

### 2.1 Data & Storage Model
- **Dependencies**: 
  - `db_dir`: Root directory for storage.
  - `chroma_path`: Sub-directory (`db_dir/chroma`) for ChromaDB persistence.
  - `distill_url`: Base URL for the distillation provider.
  - `distill_model`: Model name for distillation.
  - `distill_provider`: Protocol type (`ollama` or `openai-compatible`).
- **Storage Strategy (ChromaDB)**:
  - **Collection**: `summaries`
  - **ID**: `session_id::room_id` (or `session_id` if room_id is empty/default)
  - **Document**: The distilled summary text.
  - **Metadata**: `{"session_id": session_id, "room_id": room_id, "last_updated": float_timestamp}`.

### 2.2 Semantic Distillation Engine
- **Method signature**: `async def distill(session_id: str, traces: List[Dict[str, Any]], room_id: str = "general") -> str`
- **Unified Client**: Uses `LLMFactory.get_chat_client()` to abstract away provider-specific API logic.
- **Logic flow**:
  1. Iterate `traces` to build a conversation corpus.
  2. Construct the summarization prompt. The prompt MUST be template-based and strictly categorize extracted facts into 'Technical Decisions', 'User Preferences', and 'Project Context' to optimize for specific test dimensions (ISSUE-007).
  3. **TasteGuard (Belief Anchor)**: Apply a protective layer over the distilled summary. Core, highly-weighted subjective facts (e.g., "The user hates ORMs") are anchored and highly resistant to being overwritten or unlearned by transient, contradictory data during future distillations.
  4. Perform stateful merge: Use the LLM to merge NEW dialogue into the EXISTING summary retrieved from ChromaDB.
  5. Upsert result into the `summaries` collection.

### 2.4 Subjective Cognitive Judge (L6b Evaluator)
- **Background**: Replaces the objective "hallucination prevention" judge with a user-specific "Taste/Value Profile" judge.
- **Mechanism**: The judge must ask: "Does this context contain information relevant to the user query?" with a bias towards technical grounding.
- **Action**: Before context is finalized, an LLM call (`filter_relevant_snippets`) validates a list of context snippets against the query and returns the indices of the relevant ones, resolving the binary all-or-nothing gate issue.
- **Fail-open**: If the LLM throws an exception (e.g. timeout), all snippets are considered relevant.

### 2.5 Memory Recall Interface
- **Method signature**: `def get_summary(session_id: str, room_id: str = "general") -> Optional[str]`
- Reads and returns the latest summary for the given session from ChromaDB.

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
