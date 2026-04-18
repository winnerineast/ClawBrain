# design/management_api.md v1.1

## 1. Objective
Expand the **Management API** to support a full **Observability Dashboard**. Adds session discovery, trace inspection, and a built-in Web UI — transforming ClawBrain from a "black box" relay into a transparent memory engine.

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

#### GET `/dashboard`
Serves a static HTML single-page application.

### 2.2 Functional logic
- **Session Discovery**: Uses `Hippocampus.get_all_session_ids()`.
- **Trace Fetching**: Uses `Hippocampus.get_recent_traces(limit, context_id)`.

### 2.3 Dashboard UI (Single-File SPA)
- **Built-in Template**: Stored in `src/utils/dashboard_tpl.py`.
- **Tech Stack**: Vanilla HTML5 + CSS (Modern Dark Mode) + standard `fetch` API.
- **Layout**:
  - **Sidebar**: List of active sessions with "refresh" button.
  - **Main View**: 
    - **Header**: Session ID and Status.
    - **L3 Panel**: Markdown-rendered (simple pre-wrap) Neocortex summary.
    - **L1 Panel**: Current activation weights of Working Memory.
    - **L2 Timeline**: Scrollable list of raw interaction traces.
  - **Actions**: Floating buttons to Clear or Distill the active session.

## 3. Test Specification (TDD)

### 3.1 Session List
- Ingest data for two different sessions, call `/v1/management/sessions`, assert both IDs are present.

### 3.2 Trace API
- Ingest 5 traces, call `/v1/management/traces/{id}?limit=2`, assert 2 traces returned.

## 4. Output Targets
- `src/main.py`: Add management routes and mount the `/dashboard` HTML endpoint.
- `src/utils/dashboard_tpl.py`: Create the HTML/CSS/JS single-string template.
- `src/memory/storage.py`: Ensure `get_all_session_ids` is exposed and efficient.
