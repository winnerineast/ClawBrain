# Task: ISSUE-002 Benchmark Quality Audit & Cognitive Performance Gap Remediation

## 1. Objective
Address the performance gaps identified in Issue #3 (ISSUE-002) by optimizing the tri-layer memory system's context injection and budgeting.

## 2. Remediation Plan

### Phase 29: Neocortex Silence & Blocking Compact
- **Change**: Update `MemoryRouter.get_combined_context` to remain silent if no L3 summary exists.
- **Change**: Modify `/internal/compact` in `main.py` to be a blocking operation (await distillation).
- **Rationale**: Reduce noise for LLM and ensure distillation is complete before benchmark evaluation.

### Phase 30: Plain-Text Hippocampus
- **Change**: Refactor `MemoryRouter` to inject L2 (Hippocampus) memories as flat, human-readable bullet points instead of raw JSON.
- **Example**: `- USER: content | ASSISTANT: content`
- **Rationale**: Reduce token overhead and cognitive load for the model.

### Phase 31: Context Budgeting v2 (Priority Shift)
- **Change**: Re-prioritize memory layers to **L3 -> L1 -> L2**.
- **Change**: Implement header safety checks (only inject headers if content exists and budget permits).
- **Rationale**: Ensure active conversation (L1) is preserved over historical snippets (L2) in tight context windows.

## 3. Implementation Steps
1. Update `GEMINI.md` to formalize the Design-First workflow.
2. Surgically update `design/memory_router.md`, `design/context_engine_api.md`, and `design/benchmark.md`.
3. Apply code changes to `src/memory/router.py` and `src/main.py`.
4. Translate all Chinese comments/docstrings in `src/memory/*.py` to English (Rule 9).
5. Verify with a new test suite: `tests/test_issue_002_remediation.py`.

## 4. Verification Results
- `tests/test_issue_002_remediation.py`: 5 passed.
- All layer priorities and silence logic confirmed.
