# design/context_engine_api.md v1.1

## 1. Objective

Expose a set of **internal HTTP endpoints** that implement the four lifecycle hooks of the OpenClaw Context Engine plugin interface. These endpoints allow the `@clawbrain/openclaw` npm package (a thin TypeScript wrapper) to delegate all memory operations to the ClawBrain Python server, while giving OpenClaw native session lifecycle integration.

The endpoints are prefixed `/internal/` to signal that they are not part of the public relay API. They accept and return JSON, require no authentication (localhost-only by design), and must never be exposed on a public network interface.

## 2. OpenClaw Context Engine Contract (v1.1 Alignment)

OpenClaw calls the following four hooks on every registered context engine:

| Hook | When called | Key inputs | Expected output |
|------|-------------|-----------|-----------------|
| `ingest` | Each message arrives in a session | `sessionId`, `message {role, content}`, `isHeartbeat` | `{ ingested: bool }` |
| `assemble` | Before each model run | `sessionId`, `messages[]`, `tokenBudget` | `{ messages[], estimatedTokens, systemPromptAddition? }` |
| `compact` | Context window full, or `/compact` | `sessionId`, `force` | `{ ok: bool, compacted: bool }` |
| `afterTurn` | After each model run completes | `sessionId`, `messages[]`, `prePromptMessageCount` | _(void)_ |

## 3. Endpoint Specifications

### 3.1 POST `/internal/ingest`

**Purpose**: Archive a single raw message into the Hippocampus. In OpenClaw v2026.4.2 local mode, this hook might be skipped in favor of batch processing in `afterTurn`.

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
- Extract `intent` via `SignalDecomposer`.
- Call `hippo.save_trace(trace_id, payload, search_text=intent, context_id=session_id)`.
- Update Working Memory via `_get_wm(session_id).add_item(trace_id, intent)`.
- Call `hippo.save_wm_state(session_id, wm.items)`.
- Increment distillation counter; spawn `_auto_distill_worker` if threshold reached.

---

### 3.2 POST `/internal/assemble`

**Purpose**: Query the tri-layer memory for the given session and return a `system_prompt_addition` string.

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
- Call `get_combined_context(session_id, current_focus)` with the computed budget.
- Wrap result in `[CLAWBRAIN MEMORY]` and `[END CLAWBRAIN MEMORY]` headers.
- Return empty string (minimal header) if no memory exists.

---

### 3.3 POST `/internal/compact`

**Purpose**: Trigger Neocortex distillation and clear older Working Memory items.

**Request body**:
```json
{ "session_id": "alice", "force": false }
```

**Behaviour**:
- **Phase 29 (Blocking Compact)**: This endpoint must **await** `neo.distill` before returning to ensure distillation is complete for benchmarking.
- Fetch recent traces: `hippo.get_recent_traces(limit=distill_threshold, context_id=session_id)`.
- **Await** `neo.distill(session_id, traces)` to consolidate episodic fragments.
- Evict Working Memory items older than `CLAWBRAIN_WM_COMPACT_KEEP_RECENT` (default: 5).
- Persist pruned snapshot via `hippo.save_wm_state`.

---

### 3.4 POST `/internal/after-turn` (Fixed v1.1)

**Purpose**: Post-run housekeeping and **Batch Memory Capture**. This is the primary moment when ClawBrain captures the "Stimulus + Reaction" cycle from the OpenClaw transcript.

**Request body**:
```json
{
  "session_id": "alice",
  "new_messages": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

**Behaviour**:
- **Mandatory Validation**: If `new_messages` is an empty list, the handler **must emit a `logger.error`** (e.g., `[INT_AFTER_TURN] Error: No new messages received for turn.`) to ensure protocol visibility.
- **Ingestion**: Iterate through `new_messages`. Identify "User -> Assistant" pairs. Call `mr.ingest(user_payload, reaction=assistant_payload, context_id=session_id)` to archive the turn into Hippocampus.
- **State Persistence**: Call `hippo.save_wm_state(session_id, wm.items)` to persist the current Working Memory state.
- **Distillation Trigger**: Increment the internal distillation counter and spawn the worker if threshold is reached.

---

## 4. Shared Behaviours

### 4.1 Session creation
All endpoints call `_get_wm(session_id)` which lazily creates a per-session `WorkingMemory` instance.

### 4.2 No authentication
Endpoints bind on 11435. They rely on network-level access control (localhost binding).

### 4.3 Logging (Audit Persistence)
All endpoints must emit structured log lines:
- `[INT_INGEST]`, `[INT_ASSEMBLE]`, `[INT_COMPACT]`, `[INT_AFTER_TURN]`
- Each tag must be followed by `session_id` and action-specific metadata.

### 4.4 WM_COMPACT_KEEP_RECENT
The environment variable `CLAWBRAIN_WM_COMPACT_KEEP_RECENT` (default: 5) controls the Working Memory retention policy during compaction.

## 5. Test Specification

All tests live in `tests/test_p23_internal_api.py`.

### 5.1 Ingest Validation
- Ingest a non-heartbeat message; assert `ingested: true` and verify appearance in `hippo.get_recent_traces`.
- Ingest a heartbeat; assert no trace is created.

### 5.2 Assemble Validation
- Ingest traces for session X, call assemble; assert `system_prompt_addition` is non-empty.
- Test empty session; assert HTTP 200 and minimal headers.

### 5.3 Compact Validation
- Ingest N ≥ distill_threshold traces; call compact; assert `compacted: true`.
- Verify WM item count is ≤ `CLAWBRAIN_WM_COMPACT_KEEP_RECENT`.

### 5.4 After-Turn (v1.1) Validation
- **Negative Test**: Send empty `new_messages`; verify `logger.error` is triggered (via log inspection or mock).
- **Positive Test**: Send valid pair; verify `traces` table contains reconstructed stimulus and reaction.

## 6. Output Targets
- `src/main.py`: Implement the upgraded `/internal/after-turn` route.
- `packages/openclaw/src/engine.ts`: Implement new message extraction and atomized transmission.
