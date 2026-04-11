# design/test_sanitization.md v1.0

## 1. Objective
Establish a deterministic and sterile environment for regression testing by enforcing a "Clean Slate" policy. This ensures that every test run is independent of previous executions, preventing intermittent failures caused by lingering processes, shared database locks, or exhausted GPU resources.

## 2. Sanitization Pillars

### 2.1 Process Reaping
Before starting the test suite, the system must identify and terminate all known orphaned server processes:
- **ClawBrain Relay**: Kill any `uvicorn` instances bound to the project source.
- **LM Studio Server**: Ensure port `1234` is released if it was left running by a failed test.
- **Background Workers**: Ensure no orphaned async tasks are alive.

### 2.2 GPU & VRAM Recovery
To maximize stability for LLM-dependent tests (like Neocortex Distillation and E2E loops):
- **Ollama Reset**: Execute `ollama stop` for all currently loaded models.
- **Verification**: Ensure the GPU memory is reclaimed before the first test case begins.

### 2.3 Storage & State Purge
- **Temporary Data**: Recursively delete all content within `tests/data/` and project-local `data/` if configured for testing.
- **Internal Cache**: Explicitly reset the `_CHROMA_CLIENTS` global cache in the test runner to prevent "readonly database" errors from stale ChromaDB handles.
- **State Files**: Remove `vault_state.json` and `vault_knowledge` collections generated during previous runs.

### 2.4 Pre-flight Dependency Check
Verify that the underlying infrastructure is ready:
- **Ollama Accessibility**: Confirm `localhost:11434` is responding.
- **Environment**: Confirm `venv` is active and `PYTHONPATH` is set.

## 3. Implementation: `tests/prepare_env.py`
A Python utility will be created to perform these actions programmatically, ensuring cross-platform compatibility (Linux/macOS).

### Usage Logic:
1. `python tests/prepare_env.py --force`
2. If successful, proceed to `pytest`.
3. If failure (e.g., port stuck), exit with code 1 and log the blocker.

## 4. Integration
The `install.sh` and any future `run_regression.sh` scripts MUST call this sanitization utility as their first step.

## 5. Output Targets
- `tests/prepare_env.py`: The sanitization engine.
- `install.sh`: Integration update.
- `run_regression.sh`: A new standardized test entry point.
