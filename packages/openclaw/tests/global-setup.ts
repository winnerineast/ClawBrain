// Vitest globalSetup: start the ClawBrain Python server on a random port
// with a temp DB dir, expose the URL via process.env for integration tests.

import { spawn, ChildProcess } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const REPO_ROOT = join(import.meta.dirname, "../../..");
const PYTHON = join(REPO_ROOT, "venv/bin/python3");
const PORT = 19435; // non-conflicting test port
const TIMEOUT_MS = 15_000;

let server: ChildProcess;
let dbDir: string;

export async function setup(): Promise<void> {
  dbDir = mkdtempSync(join(tmpdir(), "clawbrain-int-"));
  process.env["CLAWBRAIN_URL"] = `http://localhost:${PORT}`;

  server = spawn(
    PYTHON,
    ["-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", String(PORT)],
    {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        CLAWBRAIN_DB_DIR: dbDir,
        CLAWBRAIN_MAX_CONTEXT_CHARS: "2000",
        PYTHONPATH: REPO_ROOT,
      },
      stdio: ["ignore", "pipe", "pipe"],
    }
  );

  server.stderr?.on("data", () => {}); // suppress noisy uvicorn logs
  server.stdout?.on("data", () => {});

  // Wait until /health responds
  const deadline = Date.now() + TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const resp = await fetch(`http://localhost:${PORT}/health`);
      if (resp.ok) return; // server is up
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`ClawBrain server did not start within ${TIMEOUT_MS}ms`);
}

export async function teardown(): Promise<void> {
  server?.kill("SIGTERM");
  await new Promise((r) => setTimeout(r, 300));
  try { rmSync(dbDir, { recursive: true, force: true }); } catch { /* ok */ }
  delete process.env["CLAWBRAIN_URL"];
}
