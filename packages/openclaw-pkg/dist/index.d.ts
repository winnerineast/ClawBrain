import { ClawBrainContextEngine } from "./engine.js";
export { ClawBrainContextEngine } from "./engine.js";
type OpenClawPluginApi = {
    registerContextEngine: (id: string, factory: () => ClawBrainContextEngine) => void;
};
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
export default function register(api: OpenClawPluginApi): void;
//# sourceMappingURL=index.d.ts.map