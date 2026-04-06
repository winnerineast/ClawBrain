type AnyContent = {
    type: string;
    [key: string]: unknown;
};
type UserMessage = {
    role: "user";
    content: string | AnyContent[];
    timestamp: number;
};
type AssistantMsg = {
    role: "assistant";
    content: string | AnyContent[];
    timestamp: number;
};
type ToolResultMsg = {
    role: "toolResult";
    [key: string]: unknown;
};
type AgentMessage = UserMessage | AssistantMsg | ToolResultMsg | {
    role: string;
    [key: string]: unknown;
};
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
type IngestResult = {
    ingested: boolean;
};
export declare class ClawBrainContextEngine {
    readonly info: ContextEngineInfo;
    ingest(params: {
        sessionId: string;
        sessionKey?: string;
        message: AgentMessage;
        isHeartbeat?: boolean;
    }): Promise<IngestResult>;
    assemble(params: {
        sessionId: string;
        sessionKey?: string;
        messages: AgentMessage[];
        tokenBudget?: number;
        model?: string;
        prompt?: string;
    }): Promise<AssembleResult>;
    compact(params: {
        sessionId: string;
        sessionKey?: string;
        sessionFile?: string;
        tokenBudget?: number;
        force?: boolean;
    }): Promise<CompactResult>;
    afterTurn(params: any): Promise<void>;
    dispose(): Promise<void>;
}
export {};
//# sourceMappingURL=engine.d.ts.map