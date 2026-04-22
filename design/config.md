# design/config.md v1.0

## 1. Objective
Enable **hot-reload** of the ClawBrain provider registry via environment variables. Currently `ProviderRegistry` and the local model whitelist are fully hard-coded; adding a new model or provider requires a source change and restart. This module enables zero-code-change extension at startup.

## 2. Architecture

### 2.1 Dynamic Provider Registration (Env-Var Injection)
- **`CLAWBRAIN_EXTRA_PROVIDERS`**: JSON string, format:
  ```json
  {"together": {"base_url": "https://api.together.xyz", "protocol": "openai"}}
  ```
  Parsed by `ProviderRegistry.__init__` at startup and merged into `self.providers`. On parse failure, silently skip and log a WARNING.

### 2.2 Local Model Whitelist Extension (Env-Var Injection)
- **`CLAWBRAIN_LOCAL_MODELS`**: JSON string, format:
  ```json
  {"llama3:8b": "ollama", "mistral:7b": "ollama"}
  ```
  Merged into `self.known_no_prefix_models` at startup. On parse failure, silently skip.

### 2.3 Session Isolation Warning
- When a request carries no `x-clawbrain-session` header and `session_id` falls back to `"default"`, the gateway must log:
  `[SESSION] No session header — using 'default'. Set 'x-clawbrain-session' for isolation.`
- This is a warning log only; the request is not blocked.

### 2.4 Cognitive Circuit Breaker (Env-Var Injection)
- **`CLAWBRAIN_CB_MAX_FAILURES`**: Integer (default: 3). Maximum failures before opening the circuit for background cognitive tasks (Room Detection, Distillation).
- **`CLAWBRAIN_CB_BACKOFF`**: Integer (default: 60). Seconds to wait before attempting to close the circuit after a failure threshold is reached.

## 3. Test Specification (TDD)

### 3.1 Env-Var Injection Validation
- Inject `CLAWBRAIN_EXTRA_PROVIDERS` and `CLAWBRAIN_LOCAL_MODELS` via `os.environ`, instantiate `ProviderRegistry`, and assert that the new provider and model are correctly routed by `resolve_provider`.

### 3.2 Invalid JSON Tolerance
- Inject a malformed JSON string; verify the system starts normally, only logs a WARNING, and does not raise an exception.

## 4. Output Targets
- `src/gateway/registry.py`: Add startup env-var parsing logic.
- `src/main.py`: Add session isolation warning log.
- `tests/test_p16_config.py`: Env-var injection and fault-tolerance tests.
