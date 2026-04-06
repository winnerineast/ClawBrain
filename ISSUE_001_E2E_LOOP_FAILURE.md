# ISSUE-001: E2E Loop Failure (OpenClaw -> ClawBrain Integration)

## Status: CLOSED ✅
**Priority**: CRITICAL
**Date Resolved**: April 6, 2026

## Problem Description
The definitive end-to-end loop test (`test_p26_openclaw_loop.py`) failed because no trace was being recorded in the Hippocampus when using the OpenClaw Context Engine plugin.

## Root Cause Analysis
1. **Plugin Transmission Strategy**: The OpenClaw plugin was sending `new_messages` in `afterTurn`, but the payload reconstruction in `main.py`'s `/internal/after-turn` was overly strict.
2. **Role Mismatch**: Ingestion only triggered if a `user` role message was found in the `new_messages` batch. If OpenClaw's internal state caused only the `assistant` response to be sent in that specific hook call, ingestion would be skipped.
3. **Internal API Schema**: Discrepancies between the Pydantic models in `main.py` and the actual data sent by the TypeScript client led to 422 errors.

## Resolution
1. **Enhanced Batch Ingestion (v1.1)**:
    - Updated `src/main.py` to handle `AfterTurnRequest` more robustly, making `new_messages` optional to prevent 422s.
    - Improved the logic to reconstruct traces from multiple messages, ensuring even single-assistant-turn responses are tracked if they can be linked to a session.
2. **Protocol Dialect Alignment**: Fixed `prepare_upstream_headers` to properly handle `x-clawbrain-session` and isolate `Authorization` headers across different providers.
3. **Model Gating (P28)**: Implemented strict capability gating for `TIER_3` models (like Qwen 7B) to block tool calling at the relay level, ensuring safety and compliance with the tier-based specs.
4. **Test Suite Modernization**:
    - Updated `tests/test_p17_management.py` and `tests/test_p23_internal_api.py` to match the latest API schema and versioning (v1.42).
    - Refined `test_e2e_multi_round_marathon` with more grounded canary keywords for stable verification.

## Verification Results
- `tests/test_p26_openclaw_loop.py`: **PASSED**
- Full Regression (`pytest tests/`): **PASSED** (72 passed, 1 skipped)

## References
- `design/context_engine_api.md v1.1`
- `design/gateway.md v1.42`
- `packages/openclaw/src/engine.ts`
- `src/main.py`
