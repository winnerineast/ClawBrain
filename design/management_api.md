# design/management_api.md v1.2

## 1. Objective
Expand the **Management API** to support "The X-Ray View". This allows users to see the exact enriched prompt (JSON body) that ClawBrain sends to the upstream LLM, resolving the "black box" mystery of context injection. It transforms the Dashboard into a powerful real-time debugging tool.

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

#### DELETE `/v1/memory/{session_id}`
Clear the Neocortex summary and Working Memory snapshot for a given session.
- Response: `{"status": "cleared", "session_id": "xxx"}`

#### POST `/v1/memory/{session_id}/distill`
Manually trigger an async distillation task for a given session.
- Returns immediately: `{"status": "distillation_triggered", "session_id": "xxx"}`

#### GET `/v1/management/sessions`
Return a list of all unique session IDs found in the Hippocampus metadata.
- Response: `{"sessions": ["sid1", "sid2", ...], "total": 2}`

#### GET `/v1/management/traces/{session_id}`
Fetch recent raw traces for a session from ChromaDB.
- Query params: `limit` (default 50)
- Response: `{"session_id": "xxx", "traces": [...]}`

#### GET `/v1/management/last_injection/{session_id}`
Returns the last complete JSON payload sent to the LLM for this session.
- Response: `{"session_id": "xxx", "payload": {...}}`

#### GET `/dashboard`
Serves a static HTML single-page application.

### 2.2 Functional logic
- **Session Discovery**: Uses `Hippocampus.get_all_session_ids()`.
- **Trace Fetching**: Uses `Hippocampus.get_recent_traces(limit, session_id)`.
- **Injection Cache**: `MemoryRouter` maintains an in-memory dictionary `_last_injections` capturing the `enriched_body` during relay.

### 2.3 Dashboard UI (Single-File SPA)
- **Built-in Template**: Stored in `src/utils/dashboard_tpl.py`.
- **Tech Stack**: Vanilla HTML5 + CSS + fetch.
- **Layout Enhancements**:
  - **X-Ray Panel**: A collapsible or prominent card showing pretty-printed JSON of the last message sent to the provider.
  - **Status Indicators**: Show if the last turn was intercepted or direct.

## 3. Test Specification (TDD)

### 3.1 Session List
- Ingest data for two different sessions, call `/v1/management/sessions`, assert both IDs are present.

### 3.2 Trace API
- Ingest 5 traces, call `/v1/management/traces/{id}?limit=2`, assert 2 traces returned.

### 3.3 X-Ray Verification
- Send a request to `/v1/chat/completions`, then call `/v1/management/last_injection/{id}`, assert the returned JSON contains `[CLAWBRAIN MEMORY]`.

## 4. Output Targets
- `src/main.py`: Add `/v1/management/last_injection` route and capture logic.
- `src/memory/router.py`: Implement `_last_injections` storage.
- `src/utils/dashboard_tpl.py`: Add X-Ray UI components.
