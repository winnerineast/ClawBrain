# ISSUE-001: E2E Loop Failure (OpenClaw -> ClawBrain Integration)

## Status: OPEN 🔴
**Priority**: CRITICAL
**Date**: April 5, 2026

## Problem Description
The definitive end-to-end loop test (`test_p26_openclaw_loop.py`) failed. While the OpenClaw CLI transaction completed successfully, no trace was recorded in the ClawBrain Hippocampus database for the corresponding session.

## Evidence
- **Test Output**: `Failed: FAILED: No trace recorded by ClawBrain for session loop-test-1775401363`
- **Logs**: `[2/3] OpenClaw transaction complete.` but verification step found no rows in SQLite `traces` table for the session ID.

## Hypothesis
1. **Plugin Communication**: The `@clawbrain/openclaw` TypeScript plugin might be failing to reach the ClawBrain server on `localhost:11435`.
2. **Endpoint Mismatch**: The plugin might be calling an incorrect URL for `/internal/ingest`.
3. **OpenClaw Loading**: OpenClaw might be failing to load or initialize the `clawbrain` context engine plugin despite the configuration.
4. **Relay vs. Plugin**: If OpenClaw is configured to hit Ollama directly on `:11434` instead of the relay on `:11435`, and the plugin is also failing, no memory capture occurs.

## Action Plan
1. [ ] Audit `packages/openclaw/src/client.ts` for the internal API URL.
2. [ ] Audit ClawBrain server logs (`results/server_startup.log`) during a manual `openclaw` run.
3. [ ] Verify OpenClaw plugin loading status via its own logs.
