# design/management_api.md v1.0

## 1. Objective
Add three **memory management endpoints** to ClawBrain, allowing external tools to inspect, clear, and manually trigger distillation for a specific session's memory — solving the current problem of memory state being completely unobservable.

## 2. Architecture

### 2.1 Endpoint Definitions

#### GET `/v1/memory/{session_id}`
Query the current memory state for a given session.
- Response JSON:
  ```json
  {
    "session_id": "xxx",
    "neocortex_summary": "...",
    "working_memory_count": 5,
    "working_memory_preview": ["intent 1", "intent 2", "intent 3"]
  }
  ```
- `neocortex_summary` is `null` when no summary exists.

#### DELETE `/v1/memory/{session_id}`
Clear the Neocortex summary and Working Memory snapshot for a given session.
- Calls `Neocortex.clear_summary(session_id)` and `Hippocampus.clear_wm_state(session_id)`.
- Response: `{"status": "cleared", "session_id": "xxx"}`

#### POST `/v1/memory/{session_id}/distill`
Manually trigger an async distillation task for a given session.
- Fires `asyncio.create_task(MemoryRouter._auto_distill_worker(session_id))`.
- Returns immediately (does not wait for LLM completion): `{"status": "distillation_triggered", "session_id": "xxx"}`

### 2.2 Neocortex New Method
- **`clear_summary(context_id: str)`**: Executes `DELETE FROM neocortex_summaries WHERE context_id = ?`.

## 3. Test Specification (TDD)

### 3.1 GET Endpoint
- Ingest several records, call GET, assert the response structure is complete and `working_memory_count` matches the actual count.

### 3.2 DELETE Endpoint
- Manually call `neo._save_summary` to write data, then call DELETE, then call GET, and assert `neocortex_summary` is null.

### 3.3 POST Trigger
- Call POST, assert HTTP 200 and `status == "distillation_triggered"`.

## 4. Output Targets
- `src/main.py`: Add the three management routes.
- `src/memory/neocortex.py`: Add `clear_summary` method.
- `tests/test_p17_management.py`: Three-endpoint acceptance tests.
