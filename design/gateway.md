# design/gateway.md v1.42

## 1. Objective
Fully implement ClawBrain Gateway protocol adaptation for major LLM providers. Build a true "universal neural translator" ensuring every platform promised in the README can receive memory-augmented requests through ClawBrain. Simultaneously, complete the structured logging system so every neural activity is fully transparent. **P27 Update: Implement Secure Header Forwarding to prevent credential leakage (Issue #1).**

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

### 2.5 Streaming Response Memory Capture (P15)
- **Background**: Streaming reactions were hard-coded as `[Streamed]`, leaving the memory system blind to all streamed sessions.
- **Fix logic (inside `stream_generator`)**:
  - Decode each chunk to UTF-8 and strip whitespace.
  - Strip the `data:` SSE prefix if present; skip `[DONE]` tokens.
  - Attempt JSON parsing: Ollama format reads `message.content`; OpenAI SSE format reads `choices[0].delta.content`.
- **After stream ends**: Join `collected_content` into a full string and call `memory_router.ingest` with the real reaction. Fall back to `[Streamed]` if the list is empty.

### 2.6 session_id Full-path Propagation (P18)
- **Background**: `main.py` extracted `session_id` from the header but did not pass it to `memory_router.ingest()`, causing all records to be written to the `"default"` session.
- **Fix**: Pass `session_id=session_id` explicitly in both the non-streaming and streaming `ingest` call sites.

### 2.7 Secure Header Forwarding (P27 - Issue #1)
- **Goal**: Prevent leakage of internal session metadata and inappropriate authentication credentials to upstream LLM providers.
- **Mandatory Header Stripping**:
  - **Internal Headers**: Automatically strip all headers starting with `x-clawbrain-` (case-insensitive).
  - **Generic Sensitive Headers**: Strip `Cookie`, `Set-Cookie`, `X-Custom-Sensitive`, and any non-standard headers that could leak client state.
- **Controlled Auth Forwarding**:
  - **Priority 1 (Static Override)**: If `ProviderConfig.api_key` is set in the registry, use it to populate the appropriate auth header (`Authorization` or `x-api-key`) and **discard** any incoming auth headers from the client.
  - **Priority 2 (Transparent Relay)**: If no static key is set, forward the client's `Authorization` or `x-api-key` header **only if it matches the target provider's protocol**.
    - `openai`, `google`, `mistral`, `together`: Forward `Authorization`.
    - `anthropic`: Forward `x-api-key`; remove `Authorization`.
    - `ollama`: Remove all auth headers by default.

## 2.8 Network Plane Isolation (Stability & Performance)
To prevent internal cognitive tasks from interfering with the main relay throughput and to ensure deterministic testing:
- **Client Separation**: The `MemoryRouter` must own an independent `httpx.AsyncClient` (the "Cognitive Client"). This client is dedicated to background tasks like `distill` and `detect_room`.
- **Non-blocking Guarantee**: Cognitive Plane tasks must never block the Relay Plane. Failures or timeouts in the Cognitive Plane (e.g., local Ollama being offline) must fail silently or log warnings without returning 5xx errors to the user.
- **Mock Integrity**: Tests must use URL-targeted mocking (e.g., `respx`) instead of global class patching (`unittest.mock.patch`). This ensures that mocks intended for the Relay Plane do not accidentally capture or interfere with Cognitive Plane requests.

## 2.9 Model Context Protocol (MCP) Integration
- **Endpoints**:
  - `GET /mcp/sse`: Establishes an SSE connection for server-to-client messages.
  - `POST /mcp/messages`: Receives client-to-server JSON-RPC messages via the standard MCP SSE transport.
- **Routing Priority**: To prevent semantic collision with the catch-all relay, MCP endpoints MUST be registered in the FastAPI application BEFORE the `gateway_relay` route. This ensures that MCP-specific control messages are not intercepted by the model-aware relay logic which expects a `model` field in the payload.

## 3. Test Specification (TDD & High-Fidelity Audit)
...

### 3.3 Secure Header Leak Audit (New)
- **Audit Case**: Send a request with `x-clawbrain-session` and `Authorization`.
- **Verification**: Mock the upstream client and assert that `x-clawbrain-session` is absent and `Authorization` is only present if appropriate for the protocol.

## 4. Output Targets
- `src/main.py`: Implement the secure header filtering and auth override logic.
- `tests/reproduce_issue_1.py`: Acceptance test for the fix.
