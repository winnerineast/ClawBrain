# design/memory_integration.md v1.4

## 1. Objective
Full integration of the neural memory system. Ensure the gateway, running in a real environment (e.g., against a live Ollama instance), automatically performs memory archival and context augmentation.

## 2. Integration Architecture

### 2.1 MemoryRouter Enhancements
- **Self-consistent initialisation**: The constructor must accept `db_dir` and pass it through to all sub-modules.
- **State restoration**: Automatically load the most recent 15 messages at startup.

### 2.2 Main Gateway Integration
- **Lifecycle**: Mount a global `MemoryRouter`. Support reading the DB path from `CLAWBRAIN_DB_DIR`.
- **Request augmentation**: Inject the enriched context as the first `role: system` message in the request message stream.
- **Response closed-loop (Fixed)**: Whether the backend responds successfully or with an error (as long as valid JSON is returned), the gateway must attempt to capture the response and call `ingest()` — ensuring interaction traces are recorded even during debugging.

## 3. Test Specification (TDD)

### 3.1 Real End-to-End Memory Echo Audit (Live Environment Smoke Test)
- **Scenario**:
  1. Send a first message to the gateway: `"The project codename is 'NEURAL-X'."`
  2. Client sends a second message: `"Recall the codename."`
- **Environment requirement**: The test must run against a live Ollama instance on port 11434.
- **Verification**:
  - The test script must first verify the canary model (e.g., `gemma4:e4b`) exists via `ollama pull`.
  - When the second request reaches the gateway, the injected System Prompt must contain the secret from round one.
- **Isolation**: The test database must be isolated via the `CLAWBRAIN_DB_DIR` environment variable.

## 4. Output Targets
- `src/main.py`: Ensure that even a backend 404 response triggers an ingest attempt if a valid payload exists.
- `tests/test_p11_integration.py`: Remove all mocks; replace with real E2E interactions.
