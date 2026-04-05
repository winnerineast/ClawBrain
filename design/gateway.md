# design/gateway.md v1.40

## 1. Objective
Fully implement ClawBrain Gateway protocol adaptation for major LLM providers (Google Gemini, Mistral, xAI, OpenRouter, etc.). Build a true "universal neural translator" ensuring every platform promised in the README can receive memory-augmented requests through ClawBrain. Simultaneously, complete the structured logging system so every neural activity is fully transparent.

## 2. Architecture

### 2.1 Extended Protocol Dialects
- **Google (Gemini)**:
  - **Translator (`to_google`)**: Convert `messages` to a `contents` array; map `role: assistant` to `model`; map `system` messages to the top-level `system_instruction` field.
- **Anthropic (Claude)**:
  - **Translator (`to_anthropic`)**: Strip `role: system` messages to the top-level `system` field; normalize role alternation (merge consecutive duplicate roles); force-inject `max_tokens` (default 4096).
- **OpenAI-compatible cluster (DeepSeek, Mistral, Grok, vLLM, OpenRouter)**:
  - **Translator (`to_openai`)**: Unified model-prefix stripping. For OpenRouter, auto-inject required web identity headers (e.g., `HTTP-Referer`).
- **Non-destructive prefix stripping rule (Bug 11 fix)**:
  - All translators (`to_google`, `to_anthropic`, `to_openai`) and the gateway entry point must follow the **non-destructive prefix stripping** rule.
  - **Core logic**: Strip only the leading gateway provider identifier via `model_name.split("/", 1)[1]`. Never use `split("/")[-1]` — doing so would truncate organization paths embedded in the model ID (e.g., `nvidia/nemotron`).

### 2.2 Provider Registry & Routing Security
- `ProviderRegistry` must include built-in mappings for: google, mistral, xai, openrouter, together, ollama, lmstudio, openai, deepseek.
- **Routing security**: If the requested model cannot be resolved by `resolve_provider` (no valid prefix and not a native Ollama model ID), the system must **strictly prohibit any silent fallback**. `resolve_provider` must return `(None, None)`; the caller raises **HTTP 501 Not Implemented**. Forwarding such requests to any backend adapter is forbidden to prevent 404 errors from protocol mismatch.

### 2.3 Dynamic Protocol Detection & Standardization
- **ProtocolDetector**: Must intercept every HTTP request and automatically infer the input protocol (Ollama / OpenAI) by analysing the payload structure.
- **Standardization hardening**: Explicitly extract `tools`, `tool_choice`, `stream`, and `options` from the raw payload's top level, `options`, or `extra_body`, and populate them in `StandardRequest`. Losing these fields during conversion is forbidden, as they are required by the downstream gating logic.

### 2.4 Structured Logging System
- **Global config**: Use a unified `logging` module with format: `[TIMESTAMP] [MODULE] [LEVEL] MESSAGE | {METADATA}`.
- **Mandatory log points**: `[DETECTOR]`, `[PIPELINE]`, `[MODEL_QUAL]`, `[HP_STOR]` (sub-logger), `[ADAPTER]`.

## 3. Test Specification (TDD & High-Fidelity Audit)

### 3.1 Cross-provider Translation Alignment Audit
- **Scenario A**: Google Gemini conversion.
- **Scenario B**: OpenRouter pass-through.
- **Scenario C**: Role alternation merging (Anthropic).
- **Scenario D**: LM Studio real-environment E2E validation.

### 3.2 Audit Display & Log Acceptance
- **Side-by-Side display**: Logs must show `Internal Standard` → `Provider Specific Dialect`.
- **Async confirmation**: Tests covering async storage or streaming must include explicit waits — **1.5 s** (storage) or **15 s** (distillation).
- **Semantic recall assertion**: In marathon long-conversation tests, the system must perform hard assertions to verify canary keywords (e.g., `Health Check` or `Observability`).
- **Adaptive real-world validation**: For local services like LM Studio, the test script must auto-discover the active model ID via `/v1/models`.

### 2.5 Streaming Response Memory Capture (P15)
- **Background**: Streaming reactions were hard-coded as `[Streamed]`, leaving the memory system blind to all streamed sessions.
- **Fix logic (inside `stream_generator`)**:
  - Decode each chunk to UTF-8 and strip whitespace.
  - Strip the `data:` SSE prefix if present; skip `[DONE]` tokens.
  - Attempt JSON parsing: Ollama format reads `message.content`; OpenAI SSE format reads `choices[0].delta.content`.
  - Any parse failure is silently ignored — it must not affect the live stream output.
- **After stream ends**: Join `collected_content` into a full string and call `memory_router.ingest` with the real reaction. Fall back to `[Streamed]` if the list is empty.

### 2.6 context_id Full-path Propagation (P18)
- **Background**: `main.py` extracted `context_id` from the header but did not pass it to `memory_router.ingest()`, causing all records to be written to the `"default"` session.
- **Fix**: Pass `context_id=context_id` explicitly in both the non-streaming and streaming `ingest` call sites.

## 5. P19 Dead Code Removal
The `src/adapters/` directory (`base.py`, `lmstudio.py`, `ollama.py`, `openai.py`, `__init__.py`) has been fully superseded by `src/gateway/translator.py` and `src/gateway/registry.py`. No import references remain. Deleted in full during P19 — no compatibility shim retained.

## 4. Output Targets
- `src/main.py`: Fix model-name truncation in Google endpoint construction.
- `src/gateway/translator.py`: Complete non-destructive prefix stripping for all dialects.
- `src/gateway/registry.py`: Maintain strict routing.
- `src/gateway/detector.py`: Maintain deep metadata extraction.
- `src/memory/router.py`: Maintain archival logic.
- `tests/test_p12_lmstudio.py`: Final regression confirmation.
