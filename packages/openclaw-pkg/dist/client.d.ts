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
export declare function callIngest(payload: IngestPayload): Promise<IngestResponse>;
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
export declare function callAssemble(payload: AssemblePayload): Promise<AssembleResponse>;
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
export declare function callCompact(payload: CompactPayload): Promise<CompactResponse>;
export type AfterTurnPayload = {
    session_id: string;
    new_messages: any[];
};
export type AfterTurnResponse = {
    ok: boolean;
    ingested_count: number;
};
export declare function callAfterTurn(payload: AfterTurnPayload): Promise<AfterTurnResponse>;
//# sourceMappingURL=client.d.ts.map