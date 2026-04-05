// Generated from design/openclaw_plugin.md v1.0
// Integration tests: ClawBrainContextEngine → real Python server.
// Requires the server to be up (started by global-setup.ts).

import { describe, it, expect } from "vitest";
import { ClawBrainContextEngine } from "../src/engine.js";

function userMsg(content: string) {
  return { role: "user" as const, content, timestamp: Date.now() };
}

function assistantMsg(text: string) {
  return {
    role: "assistant" as const,
    content: [{ type: "text", text }],
    timestamp: Date.now(),
  };
}

// One engine instance shared across tests in this file.
// Each test uses a unique sessionId so they don't interfere.
const engine = new ClawBrainContextEngine();

describe("ClawBrainContextEngine — integration (real server)", () => {

  // ── P24-INT-A: ingest ──────────────────────────────────────────────────────

  it("P24-INT-A1: ingest user message → ingested=true", async () => {
    const result = await engine.ingest({
      sessionId: "int-sess-a1",
      message: userMsg("Production DB host is db.prod.internal."),
    });
    expect(result.ingested).toBe(true);
  });

  it("P24-INT-A2: ingest heartbeat → ingested=false", async () => {
    const result = await engine.ingest({
      sessionId: "int-sess-a2",
      message: userMsg("heartbeat"),
      isHeartbeat: true,
    });
    expect(result.ingested).toBe(false);
  });

  it("P24-INT-A3: ingest assistant message → ingested=true", async () => {
    const result = await engine.ingest({
      sessionId: "int-sess-a3",
      message: assistantMsg("Understood, I will remember the DB host."),
    });
    expect(result.ingested).toBe(true);
  });

  // ── P24-INT-B: assemble ────────────────────────────────────────────────────

  it("P24-INT-B1: assemble after ingest → systemPromptAddition contains CLAWBRAIN MEMORY", async () => {
    const session = "int-sess-b1";

    await engine.ingest({
      sessionId: session,
      message: userMsg("The project stack is Python 3.12 and FastAPI."),
    });
    await engine.ingest({
      sessionId: session,
      message: assistantMsg("Got it. Python 3.12 and FastAPI noted."),
    });

    const result = await engine.assemble({
      sessionId: session,
      messages: [userMsg("What stack do we use?")],
      tokenBudget: 4096,
      prompt: "Python FastAPI project",
    });

    expect(result.systemPromptAddition).toBeDefined();
    expect(result.systemPromptAddition).toContain("CLAWBRAIN MEMORY");
    expect(result.estimatedTokens).toBeGreaterThan(0);
    // messages are returned unchanged
    expect(result.messages).toHaveLength(1);
  });

  it("P24-INT-B2: assemble on empty session → HTTP 200, no throw", async () => {
    const result = await engine.assemble({
      sessionId: "int-sess-b2-empty",
      messages: [],
      tokenBudget: 2048,
      prompt: "anything",
    });
    // Empty session → no memory addition, but must not throw
    expect(result.messages).toEqual([]);
    expect(result.estimatedTokens).toBeGreaterThanOrEqual(0);
  });

  // ── P24-INT-C: compact ─────────────────────────────────────────────────────

  it("P24-INT-C1: compact after many ingests → ok=true, compacted=true", async () => {
    const session = "int-sess-c1";

    for (let i = 0; i < 8; i++) {
      await engine.ingest({
        sessionId: session,
        message: userMsg(`Message ${i}: deployment strategy for service-${i}.`),
      });
    }

    const result = await engine.compact({ sessionId: session, force: true });

    expect(result.ok).toBe(true);
    expect(result.compacted).toBe(true);
  });

  // ── P24-INT-D: afterTurn ───────────────────────────────────────────────────

  it("P24-INT-D1: afterTurn after ingest → resolves without error", async () => {
    const session = "int-sess-d1";

    await engine.ingest({
      sessionId: session,
      message: userMsg("After-turn integration canary ZETA-99."),
    });

    await expect(engine.afterTurn({ sessionId: session })).resolves.toBeUndefined();
  });

  // ── P24-INT-E: full lifecycle ──────────────────────────────────────────────

  it("P24-INT-E1: full hook sequence ingest → assemble → afterTurn", async () => {
    const session = "int-sess-e1";

    // 1. ingest (user message arrives)
    const ingestResult = await engine.ingest({
      sessionId: session,
      message: userMsg("CANARY-SECRET-XYZ is the integration test marker."),
    });
    expect(ingestResult.ingested).toBe(true);

    // 2. assemble (before model run)
    const assembleResult = await engine.assemble({
      sessionId: session,
      messages: [userMsg("Recall the canary.")],
      tokenBudget: 4096,
      prompt: "integration test marker",
    });
    expect(assembleResult.systemPromptAddition).toBeDefined();
    expect(assembleResult.systemPromptAddition!.length).toBeGreaterThan(0);

    // 3. afterTurn (model run complete)
    await expect(engine.afterTurn({ sessionId: session })).resolves.toBeUndefined();
  });
});
