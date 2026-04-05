# design/gateway_cloud.md v1.1

## 1. Objective
Add native support for **Anthropic (Claude 3.5)** and **DeepSeek** cloud providers. The focus is strict alignment with the Anthropic Messages API specification to ensure logical determinism under heterogeneous protocol translation.

## 2. Architecture

### 2.1 Dialect Translation Enhancements
- **Anthropic translator (`to_anthropic`)**:
  - **System stripping**: Extract all `role: system` entries from the `messages` array and merge them into Anthropic's required top-level `system` string field.
  - **Mandatory field injection**: Anthropic requires `max_tokens`. If missing from the request, inject a default of 4096.
  - **Role alternation normalization**: Anthropic requires strictly alternating roles. The translator must automatically merge consecutive same-role messages (e.g., two `user` turns coalesced into one) to produce a compliant request.
  - **Streaming alignment**: Handle Anthropic-specific SSE events (e.g., `content_block_delta`) and reverse-translate them into the standard OpenAI-compatible format.
- **DeepSeek support**: Pass-through using the existing OpenAI-format relay logic.

### 2.2 Credential Pass-through & Network Security
- **Header mirroring**: For Anthropic, automatically convert `Authorization` to `x-api-key` where necessary; forward credentials as-is.
- **HTTPS adaptation**: Ensure the async connection pool supports cloud TLS connections.

## 3. Test Specification (TDD)

### 3.1 Schema Compliance Audit
- **Scenario A — Role merging**: Send a request with two consecutive `user` messages; verify the Anthropic payload merges them into one.
- **Scenario B — Required field injection**: Verify `max_tokens` is accurately populated when absent.
- **Scenario C — System mapping**: Side-by-Side display of `StandardRequest (System Message)` → `Anthropic Payload (system field)`.

### 3.2 Cloud Streaming Pass-through Audit
- Simulate cloud SSE responses; verify TTFT stability after reverse-translation.

## 4. Output Targets
- `src/gateway/translator.py`: Spec-compliant translation logic.
- `src/gateway/registry.py`: Updated provider mappings.
- `tests/test_p13_cloud_adapters.py`: Schema compliance acceptance tests.
