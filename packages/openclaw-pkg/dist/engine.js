// Generated from design/openclaw_plugin.md v1.0 / design/context_engine_api.md v1.1
// ClawBrainContextEngine: implements the OpenClaw ContextEngine interface.
// Delegates all memory operations to ClawBrain via localhost HTTP.
import { callIngest, callAssemble, callCompact, callAfterTurn, } from "./client.js";
// ── Text extraction helpers ───────────────────────────────────────────────────
function extractText(message) {
    const content = message.content;
    if (!content)
        return "";
    if (typeof content === "string")
        return content;
    if (Array.isArray(content)) {
        return content
            .map((part) => {
            if (typeof part === "string")
                return part;
            return part?.text || part?.content || "";
        })
            .filter((t) => t)
            .join(" ");
    }
    return "";
}
function warn(msg) {
    process.stderr.write(`[clawbrain-warn] ${msg}\n`);
}
// ── ClawBrainContextEngine ────────────────────────────────────────────────────
export class ClawBrainContextEngine {
    info = {
        id: "clawbrain",
        name: "ClawBrain Neural Memory Engine",
        version: "1.0.0",
        ownsCompaction: true,
    };
    // ── ingest ──────────────────────────────────────────────────────────────────
    async ingest(params) {
        const { sessionId, message, isHeartbeat } = params;
        if (isHeartbeat) {
            try {
                await callIngest({
                    session_id: sessionId,
                    role: message.role,
                    content: "",
                    is_heartbeat: true,
                });
            }
            catch { /* ignore */ }
            return { ingested: false };
        }
        if (message.role === "toolResult")
            return { ingested: false };
        const text = extractText(message);
        if (!text.trim())
            return { ingested: false };
        try {
            const resp = await callIngest({
                session_id: sessionId,
                role: message.role,
                content: text,
                is_heartbeat: false,
            });
            return { ingested: resp.ingested };
        }
        catch (err) {
            warn(`ingest failed: ${err}`);
            return { ingested: false };
        }
    }
    // ── assemble ────────────────────────────────────────────────────────────────
    async assemble(params) {
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
            const estimatedTokens = Math.ceil(resp.chars_used / 4) + messages.length * 100;
            return { messages, estimatedTokens, systemPromptAddition };
        }
        catch (err) {
            warn(`assemble failed: ${err}`);
            return { messages, estimatedTokens: 0 };
        }
    }
    // ── compact ─────────────────────────────────────────────────────────────────
    async compact(params) {
        const { sessionId, force = false } = params;
        try {
            const resp = await callCompact({ session_id: sessionId, force });
            return { ok: resp.ok, compacted: resp.compacted };
        }
        catch (err) {
            warn(`compact failed: ${err}`);
            return { ok: false, compacted: false };
        }
    }
    // ── afterTurn (Fixed v1.1) ──────────────────────────────────────────────────
    async afterTurn(params) {
        try {
            const { sessionId, messages, prePromptMessageCount } = params;
            // 1. 提取该轮次产生的新消息
            const new_messages = [];
            if (messages && messages.length > (prePromptMessageCount || 0)) {
                const rawNew = messages.slice(prePromptMessageCount || 0);
                for (const m of rawNew) {
                    if (m.role === "toolResult")
                        continue;
                    const text = extractText(m);
                    if (text.trim()) {
                        new_messages.push({ role: m.role, content: text });
                    }
                }
            }
            // 2. 原子化发送给后端结算中心
            await callAfterTurn({
                session_id: sessionId,
                new_messages: new_messages
            });
        }
        catch (err) {
            warn(`afterTurn failed: ${err}`);
        }
    }
    // ── dispose ─────────────────────────────────────────────────────────────────
    async dispose() { }
}
//# sourceMappingURL=engine.js.map