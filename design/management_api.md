# design/management_api.md v1.3

## 1. Objective
Expand the **Management API** to support "The All-in-One Visualized Flow". This allows users to monitor the information flow between the **Relay Plane** (real-time chat) and the **Cognitive Plane** (background vault scanning and L3 distillation) in a single-page view. It provides a real-time event stream of how ClawBrain enhances input context windows.

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

#### GET `/v1/management/events`
Return a chronological stream of cognitive events for both planes.
- Query params: `session_id` (optional), `limit` (default 50)
- Response JSON:
  ```json
  {
    "events": [
      {
        "timestamp": 123456789.0,
        "plane": "Relay",
        "type": "ContextEnrichment",
        "message": "Enriched context for session_1 (+1500 chars)",
        "data": { "sources": { "l3": true, "vault": 2 } }
      }
    ]
  }
  ```

#### GET `/dashboard`
Serves a static HTML single-page application with an all-in-one visualized flow.

### 2.2 Functional logic
- **Event Bus**: `MemoryRouter` maintains an in-memory buffer `_cognitive_events` (capped at 100 entries).
- **Injection Cache**: `MemoryRouter` maintains an in-memory dictionary `_last_injections` capturing the `enriched_body`.

### 2.3 Dashboard UI (All-in-One SPA)
- **Built-in Template**: Stored in `src/utils/dashboard_tpl.py`.
- **Tech Stack**: Vanilla HTML5 + CSS + Mermaid.js + fetch.
- **Layout Architecture**:
  - **Global Plane Monitor**: Real-time status of Relay and Cognitive planes.
  - **Visual Information Flow**: A dynamic diagram showing information convergence from User, Vault, and Neocortex into the LLM context.
  - **Flow Log Timeline**: A unified, color-coded feed of all system activities (Relay vs Cognitive).
  - **Interactive X-Ray**: Drill down into "Context Enrichment" events to see the exact prompt injected.

## 3. Test Specification (TDD)

### 3.1 Session List
- Ingest data for two different sessions, call `/v1/management/sessions`, assert both IDs are present.

### 3.2 Trace API
- Ingest 5 traces, call `/v1/management/traces/{id}?limit=2`, assert 2 traces returned.

### 3.3 Event Stream
- Perform a Vault scan and a Chat completion, call `/v1/management/events`, assert both Relay and Cognitive events are present.

## 4. Output Targets
- `src/main.py`: Add `/v1/management/events` route.
- `src/memory/router.py`: Implement `_log_event` and `_cognitive_events` buffer.
- `src/utils/dashboard_tpl.py`: Overhaul for All-in-One Flow UI.
