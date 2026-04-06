// Generated from design/openclaw_plugin.md v1.0
// Plugin entry point for @clawbrain/openclaw.
// Default export: the register function called by OpenClaw on plugin load.
import { ClawBrainContextEngine } from "./engine.js";
export { ClawBrainContextEngine } from "./engine.js";
/**
 * Register ClawBrain as the active OpenClaw context engine.
 *
 * OpenClaw config required:
 * ```json5
 * {
 *   plugins: {
 *     slots: { contextEngine: "clawbrain" },
 *     entries: { clawbrain: { enabled: true } },
 *     load: { paths: ["./packages/openclaw/dist/index.js"] }
 *   }
 * }
 * ```
 */
export default function register(api) {
    process.stderr.write("[clawbrain-plugin] REGISTERING CONTEXT ENGINE\n");
    api.registerContextEngine("clawbrain", () => new ClawBrainContextEngine());
}
//# sourceMappingURL=index.js.map