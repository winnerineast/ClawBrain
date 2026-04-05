// Generated from design/openclaw_plugin.md v1.0
// ClawBrainContextEngine: implements the OpenClaw ContextEngine interface.
// Delegates all memory operations to ClawBrain via localhost HTTP.

import {
  callIngest,
  callAssemble,
  callCompact,
  callAfterTurn,
} from "./client.js";

// ── Minimal local type definitions ────────────────────────────────────────────
// We reproduce the required subset of OpenClaw's ContextEngine interface types
// here so the package can be compiled without openclaw as a dependency.
// At runtime, OpenClaw injects its own interface — structural compatibility is
// all that is required (TypeScript duck typing).

type TextContent = { type: "text"; text: string };
type AnyContent = { type: string; [key: string]: unknown };

type UserMessage   = { role: "user";        content: string | AnyContent[]; timestamp: number };
type AssistantMsg  = { role: "assistant";    content: AnyContent[];          timestamp: number };
type ToolResultMsg = { role: "toolResult";   [key: string]: unknown };
type AgentMessage  = UserMessage | AssistantMsg | ToolResultMsg | { role: string; [key: string]: unknown };

type ContextEngineInfo = {
  id: string;
  name: string;
  version?: string;
  ownsCompaction?: boolean;
};

type AssembleResult = {
  messages: AgentMessage[];
  estimatedTokens: number;
  systemPromptAddition?: string;
};

type CompactResult = {
  ok: boolean;
  compacted: boolean;
  reason?: string;
  result?: {
    summary?: string;
    firstKeptEntryId?: string;
    tokensBefore: number;
    tokensAfter?: number;
    details?: unknown;
  };
};

type IngestResult = { ingested: boolean };

// ── Text extraction helpers ───────────────────────────────────────────────────

function extractText(message: AgentMessage): string {
  const role = message.role;

  if (role === "user") {
    const m = message as UserMessage;
    if (typeof m.content === "string") return m.content;
    return (m.content as AnyContent[])
      .filter((c): c is TextContent => c.type === "text")
      .map((c) => c.text)
      .join(" ");
  }

  if (role === "assistant") {
    const m = message as AssistantMsg;
    return m.content
      .filter((c): c is TextContent => c.type === "text")
      .map((c) => c.text)
      .join(" ");
  }

  // toolResult and custom roles: no extractable text
  return "";
}

// ── Log helper ────────────────────────────────────────────────────────────────

function warn(msg: string): void {
  console.warn(`[clawbrain] ${msg}`);
}

// ── ClawBrainContextEngine ────────────────────────────────────────────────────

export class ClawBrainContextEngine {
  readonly info: ContextEngineInfo = {
    id: "clawbrain",
    name: "ClawBrain Neural Memory Engine",
    version: "1.0.0",
    ownsCompaction: true,
  };

  // ── ingest ──────────────────────────────────────────────────────────────────

  async ingest(params: {
    sessionId: string;
    message: AgentMessage;
    isHeartbeat?: boolean;
  }): Promise<IngestResult> {
    const { sessionId, message, isHeartbeat } = params;

    if (isHeartbeat) {
      try {
        await callIngest({
          session_id: sessionId,
          role: message.role,
          content: "",
          is_heartbeat: true,
        });
      } catch {
        // heartbeat errors are always silently swallowed
      }
      return { ingested: false };
    }

    // Skip non-text roles
    if (message.role === "toolResult") {
      return { ingested: false };
    }

    const text = extractText(message);
    if (!text.trim()) {
      return { ingested: false };
    }

    try {
      const resp = await callIngest({
        session_id: sessionId,
        role: message.role,
        content: text,
        is_heartbeat: false,
      });
      return { ingested: resp.ingested };
    } catch (err) {
      warn(`ingest failed for session=${sessionId}: ${err}`);
      return { ingested: false };
    }
  }

  // ── assemble ────────────────────────────────────────────────────────────────

  async assemble(params: {
    sessionId: string;
    messages: AgentMessage[];
    tokenBudget?: number;
    prompt?: string;
  }): Promise<AssembleResult> {
    const { sessionId, messages, tokenBudget = 4096, prompt = "" } = params;

    try {
      const resp = await callAssemble({
        session_id: sessionId,
        current_focus: prompt,
        token_budget: tokenBudget,
      });

      const systemPromptAddition = resp.system_prompt_addition.trim()
        ? resp.system_prompt_addition
        : undefined;

      // Rough token estimate: ClawBrain chars + original message payload
      const estimatedTokens =
        Math.ceil(resp.chars_used / 4) + messages.length * 100;

      return { messages, estimatedTokens, systemPromptAddition };
    } catch (err) {
      warn(`assemble failed for session=${sessionId}: ${err}`);
      return { messages, estimatedTokens: 0 };
    }
  }

  // ── compact ─────────────────────────────────────────────────────────────────

  async compact(params: {
    sessionId: string;
    force?: boolean;
  }): Promise<CompactResult> {
    const { sessionId, force = false } = params;

    try {
      const resp = await callCompact({ session_id: sessionId, force });
      return { ok: resp.ok, compacted: resp.compacted };
    } catch (err) {
      warn(`compact failed for session=${sessionId}: ${err}`);
      return { ok: false, compacted: false, reason: String(err) };
    }
  }

  // ── afterTurn ───────────────────────────────────────────────────────────────

  async afterTurn(params: { sessionId: string }): Promise<void> {
    try {
      await callAfterTurn({ session_id: params.sessionId });
    } catch {
      // best-effort; errors are silently swallowed
    }
  }

  // ── dispose ─────────────────────────────────────────────────────────────────

  async dispose(): Promise<void> {
    // No persistent resources to release (stateless HTTP client)
  }
}
