// Generated from design/openclaw_plugin.md v1.0
// HTTP client for ClawBrain's /internal/* endpoints.
// All methods degrade gracefully on network or server errors.

const DEFAULT_URL = "http://localhost:11435";
const DEFAULT_TIMEOUT_MS = 5000;

function baseUrl(): string {
  return process.env["CLAWBRAIN_URL"] ?? DEFAULT_URL;
}

function timeoutMs(): number {
  const raw = process.env["CLAWBRAIN_TIMEOUT_MS"];
  return raw ? parseInt(raw, 10) : DEFAULT_TIMEOUT_MS;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs());
  try {
    const resp = await fetch(`${baseUrl()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!resp.ok) {
      throw new Error(`ClawBrain HTTP ${resp.status} on ${path}`);
    }
    return (await resp.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

// ── /internal/ingest ──────────────────────────────────────────────────────────

export type IngestPayload = {
  session_id: string;
  role: string;
  content: string;
  is_heartbeat: boolean;
};

export type IngestResponse = {
  trace_id: string | null;
  ingested: boolean;
};

export async function callIngest(payload: IngestPayload): Promise<IngestResponse> {
  return post<IngestResponse>("/internal/ingest", payload);
}

// ── /internal/assemble ────────────────────────────────────────────────────────

export type AssemblePayload = {
  session_id: string;
  current_focus: string;
  token_budget: number;
};

export type AssembleResponse = {
  system_prompt_addition: string;
  chars_used: number;
  budget_chars: number;
};

export async function callAssemble(payload: AssemblePayload): Promise<AssembleResponse> {
  return post<AssembleResponse>("/internal/assemble", payload);
}

// ── /internal/compact ─────────────────────────────────────────────────────────

export type CompactPayload = {
  session_id: string;
  force: boolean;
};

export type CompactResponse = {
  ok: boolean;
  compacted: boolean;
  traces_distilled: number;
  wm_pruned: number;
};

export async function callCompact(payload: CompactPayload): Promise<CompactResponse> {
  return post<CompactResponse>("/internal/compact", payload);
}

// ── /internal/after-turn ──────────────────────────────────────────────────────

export type AfterTurnPayload = {
  session_id: string;
};

export type AfterTurnResponse = {
  ok: boolean;
};

export async function callAfterTurn(payload: AfterTurnPayload): Promise<AfterTurnResponse> {
  return post<AfterTurnResponse>("/internal/after-turn", payload);
}
