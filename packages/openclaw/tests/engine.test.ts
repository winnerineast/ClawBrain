// Generated from design/openclaw_plugin.md v1.0
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ClawBrainContextEngine } from "../src/engine.js";

// ── Mock fetch globally ───────────────────────────────────────────────────────

function mockFetchOk(body: unknown): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(body),
    })
  );
}

function mockFetchNetworkError(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new Error("ECONNREFUSED"))
  );
}

function lastFetchBody(): unknown {
  const mockFn = vi.mocked(fetch);
  const call = mockFn.mock.calls[0];
  return JSON.parse(call[1]?.body as string);
}

function lastFetchPath(): string {
  const mockFn = vi.mocked(fetch);
  const url = mockFn.mock.calls[0][0] as string;
  return new URL(url).pathname;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function userMsg(content: string) {
  return { role: "user" as const, content, timestamp: Date.now() };
}

function assistantMsg(texts: string[]) {
  return {
    role: "assistant" as const,
    content: texts.map((t) => ({ type: "text", text: t })),
    timestamp: Date.now(),
  };
}

function toolResultMsg() {
  return {
    role: "toolResult" as const,
    toolCallId: "tc-1",
    toolName: "Read",
    content: [{ type: "text", text: "file contents" }],
    isError: false,
    timestamp: Date.now(),
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ClawBrainContextEngine", () => {
  let engine: ClawBrainContextEngine;

  beforeEach(() => {
    engine = new ClawBrainContextEngine();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── P24-A: ingest ──────────────────────────────────────────────────────────

  it("P24-A1: ingest normal user message → POST /internal/ingest, ingested=true", async () => {
    mockFetchOk({ trace_id: "abc-123", ingested: true });

    const result = await engine.ingest({
      sessionId: "sess-1",
      message: userMsg("Deploy NEURAL-X to k8s."),
      isHeartbeat: false,
    });

    expect(result.ingested).toBe(true);
    expect(lastFetchPath()).toBe("/internal/ingest");

    const body = lastFetchBody() as Record<string, unknown>;
    expect(body["session_id"]).toBe("sess-1");
    expect(body["role"]).toBe("user");
    expect(body["content"]).toBe("Deploy NEURAL-X to k8s.");
    expect(body["is_heartbeat"]).toBe(false);
  });

  it("P24-A2: ingest heartbeat → is_heartbeat=true, ingested=false (no throw)", async () => {
    mockFetchOk({ trace_id: null, ingested: false });

    const result = await engine.ingest({
      sessionId: "sess-1",
      message: userMsg("heartbeat"),
      isHeartbeat: true,
    });

    expect(result.ingested).toBe(false);
    const body = lastFetchBody() as Record<string, unknown>;
    expect(body["is_heartbeat"]).toBe(true);
  });

  it("P24-A3: ingest toolResult role → skipped, ingested=false (no fetch call)", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await engine.ingest({
      sessionId: "sess-1",
      message: toolResultMsg(),
      isHeartbeat: false,
    });

    expect(result.ingested).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("P24-A4: ingest assistant message → text extracted from content array", async () => {
    mockFetchOk({ trace_id: "xyz-456", ingested: true });

    const result = await engine.ingest({
      sessionId: "sess-2",
      message: assistantMsg(["I will use", " Python 3.12."]),
    });

    expect(result.ingested).toBe(true);
    const body = lastFetchBody() as Record<string, unknown>;
    expect(body["role"]).toBe("assistant");
    expect(body["content"]).toBe("I will use  Python 3.12.");
  });

  // ── P24-B: assemble ────────────────────────────────────────────────────────

  it("P24-B1: assemble → POST /internal/assemble, systemPromptAddition non-empty", async () => {
    mockFetchOk({
      system_prompt_addition: "[CLAWBRAIN MEMORY]\nfact: uses Python 3.12\n[END CLAWBRAIN MEMORY]",
      chars_used: 60,
      budget_chars: 2000,
    });

    const messages = [userMsg("What language?")];
    const result = await engine.assemble({
      sessionId: "sess-3",
      messages,
      tokenBudget: 4096,
      prompt: "Python FastAPI project",
    });

    expect(result.messages).toBe(messages); // same reference, unchanged
    expect(result.systemPromptAddition).toContain("CLAWBRAIN MEMORY");
    expect(result.estimatedTokens).toBeGreaterThan(0);
    expect(lastFetchPath()).toBe("/internal/assemble");

    const body = lastFetchBody() as Record<string, unknown>;
    expect(body["session_id"]).toBe("sess-3");
    expect(body["current_focus"]).toBe("Python FastAPI project");
    expect(body["token_budget"]).toBe(4096);
  });

  it("P24-B2: assemble empty server response → systemPromptAddition is undefined", async () => {
    mockFetchOk({ system_prompt_addition: "", chars_used: 0, budget_chars: 2000 });

    const result = await engine.assemble({
      sessionId: "empty-session",
      messages: [],
    });

    expect(result.systemPromptAddition).toBeUndefined();
    expect(result.messages).toEqual([]);
  });

  // ── P24-C: compact ─────────────────────────────────────────────────────────

  it("P24-C1: compact → POST /internal/compact, returns ok=true compacted=true", async () => {
    mockFetchOk({ ok: true, compacted: true, traces_distilled: 8, wm_pruned: 3 });

    const result = await engine.compact({ sessionId: "sess-4", force: true });

    expect(result.ok).toBe(true);
    expect(result.compacted).toBe(true);
    expect(lastFetchPath()).toBe("/internal/compact");

    const body = lastFetchBody() as Record<string, unknown>;
    expect(body["session_id"]).toBe("sess-4");
    expect(body["force"]).toBe(true);
  });

  // ── P24-D: afterTurn ───────────────────────────────────────────────────────

  it("P24-D1: afterTurn → POST /internal/after-turn, resolves without error", async () => {
    mockFetchOk({ ok: true });

    await expect(
      engine.afterTurn({ sessionId: "sess-5" })
    ).resolves.toBeUndefined();

    expect(lastFetchPath()).toBe("/internal/after-turn");
    const body = lastFetchBody() as Record<string, unknown>;
    expect(body["session_id"]).toBe("sess-5");
  });

  // ── P24-E: graceful degradation ────────────────────────────────────────────

  it("P24-E1: network error in ingest → returns ingested=false, no throw", async () => {
    mockFetchNetworkError();

    const result = await engine.ingest({
      sessionId: "offline",
      message: userMsg("hello"),
    });

    expect(result.ingested).toBe(false);
  });

  it("P24-E2: network error in assemble → returns original messages, no throw", async () => {
    mockFetchNetworkError();

    const messages = [userMsg("what?")];
    const result = await engine.assemble({
      sessionId: "offline",
      messages,
    });

    expect(result.messages).toBe(messages);
    expect(result.estimatedTokens).toBe(0);
    expect(result.systemPromptAddition).toBeUndefined();
  });
});
