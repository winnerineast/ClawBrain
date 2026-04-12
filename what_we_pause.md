# Task Pause Summary: Universal Hub Transformation (v2.0)

## 1. Current Progress (The "Universal Hub" Shift)
*   **✅ Architectural Decoupling**: Relay Plane and Cognitive Plane are now fully separated. The server boots in <50ms, with memory hydration and vault indexing running as independent background pulses.
*   **✅ Professional CLI**: `src/cli.py` implemented with a `mempalace`-style dispatch pattern. Verified via `test_p37` (Status command passes).
*   **✅ MCP Dual-Mode**: Standard MCP server implemented.
    *   **integrated (SSE)**: Mounted as a raw ASGI app to resolve double-response conflicts.
    *   **standalone (Stdio)**: Implemented "Thin Client" logic to prevent database lock conflicts (Single Storage Ownership).
*   **✅ State Machine**: Replaced `hasattr` hacks with a formal `EngineState` (`INITIALIZING` -> `READY`). All endpoints are now protected by `check_ready` guards.
*   **✅ Test Acceleration**: `prepare_env.py` now supports **Cognitive Snapshots**, restoring pre-warmed databases in milliseconds.

## 2. The Persistent Blocker: "The Ghost 500 Error"
*   **Symptom**: `tests/test_p37_cli_integration.py` fails on the `ingest` command with a `500 Internal Server Error`.
*   **The Paradox**: 
    *   Manual code audit of `src/main.py` and `src/memory/router.py` confirms that the `TypeError` (mismatched arguments) was fixed.
    *   MCP test (`test_p38`) passes the same logic, yet CLI fails.
*   **Hypothesis**: There is a mismatch in how `uvicorn` is spawning the test server instance, potentially loading stale bytecode or an inconsistent environment configuration during the `pytest` lifecycle.

## 3. Next Steps (Action Plan for Tomorrow)
1.  **Deep Traceback Audit**: Force the test server to log to a physical file during the failing CLI test to capture the *exact* Python traceback.
2.  **Environment Sanitation**: Investigate if the `tests/data/cli_test_db` cleanup is interacting poorly with the background `_startup_routine`.
3.  **MCP Interoperability**: Finalize the conversion of `AnyUrl` to `str` in the MCP client tests to ensure 100% deterministic resource validation.
4.  **Final Release**: Merge the v2.0 interfaces and update the documentation to reflect ClawBrain as a universal agent memory tool.

## 4. Design Debt
*   **Issue #19**: Sparse Data Fallback (BM25/Exact match needed).
*   **Issue #20**: Realistic Temporal Distillation Tests.
