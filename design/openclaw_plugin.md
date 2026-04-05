# design/openclaw_plugin.md v1.0

## 1. Objective

Deliver `@clawbrain/openclaw` — a TypeScript npm package that registers
ClawBrain as an OpenClaw **Context Engine plugin**. The plugin implements
OpenClaw's `ContextEngine` interface by forwarding all four lifecycle hooks
to the ClawBrain Python server's `/internal/*` endpoints over localhost HTTP.

No memory logic lives in the plugin itself. It is a thin HTTP bridge.

## 2. Architecture

```
OpenClaw runtime
    │
    │  ingest / assemble / compact / afterTurn
    ▼
@clawbrain/openclaw (TypeScript, ~200 LOC)
    │
    │  POST http://localhost:11435/internal/*
    ▼
ClawBrain Python server (src/main.py)
    │
    ├─ Hippocampus  (SQLite FTS5 archive)
    ├─ WorkingMemory (in-process attractor dynamics)
    └─ Neocortex    (async LLM distillation)
```

The plugin is a pure pass-through adapter. All intelligence lives in the
Python server.

## 3. Package Structure

```
packages/openclaw/
  package.json          # @clawbrain/openclaw, ESM, Node ≥ 18
  tsconfig.json
  src/
    client.ts           # Typed fetch wrappers for /internal/* endpoints
    engine.ts           # ClawBrainContextEngine implements ContextEngine
    index.ts            # Plugin entry: default export = register(api)
  tests/
    engine.test.ts      # Vitest unit tests with mocked fetch
```

## 4. Configuration

### 4.1 Environment variables (read by the plugin at runtime)

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLAWBRAIN_URL` | `http://localhost:11435` | Base URL of the ClawBrain server |
| `CLAWBRAIN_TIMEOUT_MS` | `5000` | Per-request timeout in milliseconds |

### 4.2 User openclaw.json

```json5
{
  plugins: {
    slots: { contextEngine: "clawbrain" },
    entries: {
      "clawbrain": {
        enabled: true,
        config: {
          // Optional: override server URL
          // url: "http://localhost:11435"
        }
      }
    },
    load: { paths: ["./packages/openclaw/dist/index.js"] }
  }
}
```

## 5. Interface Mapping

### 5.1 `ingest`

OpenClaw calls `ingest` for every new message.

**Input mapping:**
```
sessionId       → body.session_id
message.role    → body.role   (only "user" / "assistant" mapped; others skipped)
message.content → body.content (text extracted; non-text messages skipped)
isHeartbeat     → body.is_heartbeat
```

**Content extraction rules:**
- `role === "user"`: content is `string` → use directly; array → join TextContent items.
- `role === "assistant"`: content array → join TextContent items.
- `role === "toolResult"`: skip (no semantic text to archive).
- Empty extracted text → treat as heartbeat (return `{ ingested: false }`).

**Return:**
```
{ trace_id, ingested } → { ingested }
```

### 5.2 `assemble`

OpenClaw calls `assemble` before each model run.

**Input mapping:**
```
sessionId    → body.session_id
prompt       → body.current_focus  (the current user prompt, used for retrieval)
tokenBudget  → body.token_budget
```

**Behaviour:**
- Call `POST /internal/assemble` on ClawBrain.
- Return the original `messages` array unchanged (ClawBrain does not filter messages).
- Put ClawBrain's `system_prompt_addition` in `AssembleResult.systemPromptAddition`.
- Estimate tokens: `Math.ceil(chars_used / 4)` as a rough heuristic, plus the
  original message token estimate (`messages.length * 100` as a safe fallback
  when no better signal is available).

**Return:**
```typescript
{
  messages,                   // unchanged original messages
  estimatedTokens,            // chars_used / 4 + messages.length * 100
  systemPromptAddition,       // from ClawBrain (empty string → undefined)
}
```

### 5.3 `compact`

**Input mapping:**
```
sessionId → body.session_id
force     → body.force
```

**Return:**
```
{ ok, compacted } from ClawBrain → CompactResult { ok, compacted }
```
ClawBrain does not return `firstKeptEntryId` or token counts; these fields are
omitted (optional in the interface).

### 5.4 `afterTurn`

**Input mapping:**
```
sessionId → body.session_id
```
All other params (messages, prePromptMessageCount, etc.) are ignored — ClawBrain
tracks its own state server-side.

**Return:** `void` (after-turn has no required return value).

## 6. Error Handling

- Network errors (server unreachable, timeout): log a warning and return a safe
  no-op result (`{ ingested: false }`, `{ messages, estimatedTokens: 0 }`, etc.)
  rather than throwing. ClawBrain is an enhancement, not a dependency.
- HTTP 4xx/5xx: same policy — degrade gracefully, log the status.
- `afterTurn` errors are swallowed silently (void return, best-effort).

## 7. Test Specification

Tests live in `tests/engine.test.ts` (Vitest). `fetch` is mocked globally.

| Test | Description |
|------|-------------|
| P24-A1 | `ingest` normal user message → POST to `/internal/ingest`, returns `{ ingested: true }` |
| P24-A2 | `ingest` heartbeat → `is_heartbeat: true`, returns `{ ingested: false }` |
| P24-A3 | `ingest` toolResult role → skipped, returns `{ ingested: false }` |
| P24-A4 | `ingest` assistant message → text extracted from content array |
| P24-B1 | `assemble` → POST to `/internal/assemble`, `systemPromptAddition` non-empty |
| P24-B2 | `assemble` empty server response → `systemPromptAddition` is undefined |
| P24-C1 | `compact` → POST to `/internal/compact`, returns `{ ok: true, compacted: true }` |
| P24-D1 | `afterTurn` → POST to `/internal/after-turn`, resolves without error |
| P24-E1 | Network error in `ingest` → returns `{ ingested: false }` (no throw) |
| P24-E2 | Network error in `assemble` → returns original messages (no throw) |

## 8. Output Targets

- `design/openclaw_plugin.md` (this file): authoritative spec.
- `packages/openclaw/package.json`
- `packages/openclaw/tsconfig.json`
- `packages/openclaw/src/client.ts`
- `packages/openclaw/src/engine.ts`
- `packages/openclaw/src/index.ts`
- `packages/openclaw/tests/engine.test.ts`
