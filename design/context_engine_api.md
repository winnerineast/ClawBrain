# design/context_engine_api.md v1.0

## 1. Objective

Expose a set of **internal HTTP endpoints** that implement the four lifecycle hooks
of the OpenClaw Context Engine plugin interface. These endpoints allow the future
`@clawbrain/openclaw` npm package (a thin TypeScript wrapper) to delegate all
memory operations to the ClawBrain Python server, while giving OpenClaw native
session lifecycle integration.

The endpoints are prefixed `/internal/` to signal that they are not part of the
public relay API. They accept and return JSON, require no authentication (they are
localhost-only by design), and must never be exposed on a public network interface.

## 2. OpenClaw Context Engine Contract

OpenClaw calls the following four hooks on every registered context engine:

| Hook | When called | Key inputs | Expected output |
|------|-------------|-----------|-----------------|
| `ingest` | Each message arrives in a session | `sessionId`, `message {role, content}`, `isHeartbeat` | `{ ingested: bool }` |
| `assemble` | Before each model run | `sessionId`, `messages[]`, `tokenBudget` | `{ messages[], estimatedTokens, systemPromptAddition? }` |
| `compact` | Context window full, or `/compact` | `sessionId`, `force` | `{ ok: bool, compacted: bool }` |
| `afterTurn` | After each model run completes | `sessionId` | _(void)_ |

ClawBrain maps each hook to one internal endpoint. The TypeScript plugin calls
these endpoints over localhost HTTP; no shared process, no FFI.

## 3. Endpoint Specifications

### 3.1 POST `/internal/ingest`

**Purpose**: Archive a single raw message into the Hippocampus and update the
session's Working Memory snapshot. Equivalent to the `ingest` hook.

**Request body**:
```json
{
  "session_id": "alice",
  "role": "user",
  "content": "The deployment target is k8s-prod-eu.",
  "is_heartbeat": false
}
```

**Behaviour**:
- If `is_heartbeat` is true, skip archival (heartbeat messages carry no semantic content).
- Extract `intent = SignalDecomposer.extract_core_intent({"messages": [{"role": role, "content": content}]})`.
- Call `hippo.save_trace(trace_id, payload, search_text=intent, context_id=session_id)`.
- Call `_get_wm(session_id).add_item(trace_id, intent)`.
- Call `hippo.save_wm_state(session_id, wm.items)`.
- Increment distillation counter; spawn `_auto_distill_worker` if threshold reached.

**Response**:
```json
{ "trace_id": "uuid", "ingested": true }
```

**Error**: HTTP 400 if `session_id` or `content` is missing.

---

### 3.2 POST `/internal/assemble`

**Purpose**: Query the tri-layer memory for the given session and return a
`system_prompt_addition` string to be prepended to OpenClaw's system prompt.
Equivalent to the `assemble` hook.

**Request body**:
```json
{
  "session_id": "alice",
  "current_focus": "deployment target kubernetes",
  "token_budget": 4096
}
```

**Behaviour**:
- Compute `char_budget = min(token_budget * 3, CLAWBRAIN_MAX_CONTEXT_CHARS)`.
  (Rough heuristic: 1 token ≈ 3 chars; hard cap by env var.)
- Call `get_combined_context(session_id, current_focus)` with the computed budget.
- Wrap the result in a brief header:
  ```
  [CLAWBRAIN MEMORY — injected by ClawBrain context engine]
  <context>
  [END CLAWBRAIN MEMORY]
  ```
- Return this string as `system_prompt_addition`.

**Response**:
```json
{
  "system_prompt_addition": "...",
  "chars_used": 1847,
  "budget_chars": 2000
}
```

**Error**: HTTP 400 if `session_id` is missing. Never raises on empty memory —
returns an empty `system_prompt_addition` instead.

---

### 3.3 POST `/internal/compact`

**Purpose**: Trigger Neocortex distillation for the session and clear older
Working Memory items, giving OpenClaw a clean session transcript. Equivalent
to the `compact` hook with `ownsCompaction: true`.

**Request body**:
```json
{ "session_id": "alice", "force": false }
```

**Behaviour**:
- Fetch recent traces from Hippocampus: `hippo.get_recent_traces(limit=distill_threshold, context_id=session_id)`.
- Deserialise and pass to `neo.distill(session_id, traces)` — this consolidates
  episodic fragments into a persistent semantic summary in `neocortex_summaries`.
- Evict Working Memory items older than `WM_COMPACT_KEEP_RECENT` (default: 5)
  from the in-memory WM and persist the pruned snapshot via `hippo.save_wm_state`.
- Log `[COMPACT] session={session_id} traces_distilled={N} wm_kept={K}`.

**Design note**: Unlike the HTTP relay path where ClawBrain does not touch the
session transcript, in Context Engine mode the plugin's `compact()` is what
OpenClaw calls instead of its own built-in summarisation. ClawBrain distils into
SQLite; the session transcript cleanup is left to OpenClaw (it receives
`compacted: true` and handles its own transcript housekeeping).

**Response**:
```json
{ "ok": true, "compacted": true, "traces_distilled": 42, "wm_pruned": 10 }
```

---

### 3.4 POST `/internal/after-turn`

**Purpose**: Post-run housekeeping — persist Working Memory snapshot and
optionally trigger background distillation. Equivalent to the `afterTurn` hook.

**Request body**:
```json
{ "session_id": "alice" }
```

**Behaviour**:
- Call `hippo.save_wm_state(session_id, wm.items)` to persist the current
  Working Memory state.
- Increment the internal distillation counter. If the counter reaches
  `distill_threshold`, spawn `_auto_distill_worker(session_id)` as an async
  background task.

**Response**:
```json
{ "ok": true }
```

---

## 4. Shared Behaviours

### 4.1 Session creation
All endpoints call `_get_wm(session_id)` which lazily creates a per-session
`WorkingMemory` instance if one does not already exist. No explicit session
initialisation endpoint is required.

### 4.2 No authentication
These endpoints bind on the same port as the public relay (11435). They rely
on network-level access control (localhost binding, Docker network isolation).
A future version may add a shared secret header.

### 4.3 Logging
All four endpoints emit structured log lines using existing tags:
- `[INT_INGEST]`, `[INT_ASSEMBLE]`, `[INT_COMPACT]`, `[INT_AFTER_TURN]`

### 4.4 WM_COMPACT_KEEP_RECENT
New env var controlling how many recent Working Memory items to retain after
a compact call (default: 5). Accessible via `int(os.getenv("CLAWBRAIN_WM_COMPACT_KEEP_RECENT", "5"))`.

## 5. Test Specification

All tests live in `tests/test_p23_internal_api.py`. The FastAPI `TestClient`
is used; no live OpenClaw instance is required.

### 5.1 POST /internal/ingest
- Ingest a non-heartbeat message; assert `ingested: true` and verify the trace
  appears in `hippo.get_recent_traces`.
- Ingest a heartbeat (`is_heartbeat: true`); assert no trace is created.
- Missing `session_id` → HTTP 400.

### 5.2 POST /internal/assemble
- Ingest two traces for session X, then call assemble; assert `system_prompt_addition`
  is non-empty and contains expected content.
- Empty session (no prior traces) → assert `system_prompt_addition` is empty string
  or minimal header, and HTTP 200 (never an error).

### 5.3 POST /internal/compact
- Ingest N ≥ distill_threshold traces; call compact; assert response
  `compacted: true` and `traces_distilled > 0`.
- After compact, WM item count must be ≤ WM_COMPACT_KEEP_RECENT.

### 5.4 POST /internal/after-turn
- Call after-turn; assert HTTP 200 and `ok: true`.
- Verify WM snapshot is persisted to `wm_state` table after the call.

## 6. Output Targets
- `src/main.py`: four new `/internal/*` routes.
- `tests/test_p23_internal_api.py`: acceptance tests.
- `design/context_engine_api.md` (this file): authoritative spec.
