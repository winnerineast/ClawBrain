// Generated from design/openclaw_plugin.md v1.0
// HTTP client for ClawBrain's /internal/* endpoints.
// All methods degrade gracefully on network or server errors.
const DEFAULT_URL = "http://127.0.0.1:11435";
const DEFAULT_TIMEOUT_MS = 5000;
function baseUrl() {
    return process.env["CLAWBRAIN_URL"] ?? DEFAULT_URL;
}
function timeoutMs() {
    const env = process.env["CLAWBRAIN_TIMEOUT_MS"];
    return env ? parseInt(env, 10) : DEFAULT_TIMEOUT_MS;
}
async function post(path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs());
    try {
        const url = baseUrl();
        const resp = await fetch(`${url}${path}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            signal: controller.signal,
        });
        if (!resp.ok) {
            throw new Error(`ClawBrain HTTP ${resp.status} on ${path}`);
        }
        return (await resp.json());
    }
    finally {
        clearTimeout(timer);
    }
}
export async function callIngest(payload) {
    return post("/internal/ingest", payload);
}
export async function callAssemble(payload) {
    return post("/internal/assemble", payload);
}
export async function callCompact(payload) {
    return post("/internal/compact", payload);
}
export async function callAfterTurn(payload) {
    return post("/internal/after-turn", payload);
}
//# sourceMappingURL=client.js.map