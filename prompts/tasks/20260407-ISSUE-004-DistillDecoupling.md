# Task: ISSUE-004 Distillation Backend Decoupling

## 1. Objective
Enable distillation (Neocortex L3) to use any local or cloud provider (OMLX, Ollama, LM Studio, OpenAI) by making the URL, model, and API protocol configurable via environment variables.

## 2. Remediation Plan

### Phase 35: Universal Distiller Configuration
- **Change**: Refactor `Neocortex.__init__` to prioritize:
  - `CLAWBRAIN_DISTILL_URL` (e.g., `http://localhost:11434` or `http://localhost:8080/v1`)
  - `CLAWBRAIN_DISTILL_MODEL` (no hardcoded default like `gemma4:e4b`)
  - `CLAWBRAIN_DISTILL_API_KEY` (for cloud or auth-protected backends)
  - `CLAWBRAIN_DISTILL_PROVIDER` (e.g., `ollama` or `openai-compatible`)

### Phase 36: Multi-Protocol Dispatch
- **Change**: Update `Neocortex.distill` to detect the provider type:
  - If `ollama`: Use `/api/generate`.
  - If `openai` (Default): Use `/chat/completions`.
- **Rationale**: Support the widest range of local and remote backends.

### Phase 37: Design Doc Alignment
- **Change**: Update `design/memory_neocortex.md` to reflect the new dynamic configuration.

## 3. Implementation Steps
1. Surgically update `design/memory_neocortex.md`.
2. Apply code changes to `src/memory/neocortex.py`.
3. Update `src/main.py` lifespan to pass the correct URL from env.
4. Verify with a mock test case.

## 4. Verification Results
- Goal: Successful distillation call to a mock endpoint using OpenAI-style payloads.
