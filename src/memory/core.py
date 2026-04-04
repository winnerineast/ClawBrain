# Generated from design/memory.md v1.8
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional

class TraceStatus(str, Enum):
    PENDING = "STIMULUS_RECEIVED"
    COMMITTED = "REACTION_COMPLETED"
    ORPHAN = "INCOMPLETE_INTENT"

class InteractionTrace:
    def __init__(self, stimulus: Dict[str, Any], trace_id: str = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.timestamp = time.time()
        self.stimulus = stimulus
        self.reaction = None
        self.status = TraceStatus.PENDING

    def commit(self, reaction: Dict[str, Any]):
        self.reaction = reaction
        self.status = TraceStatus.COMMITTED

    def mark_orphan(self):
        self.status = TraceStatus.ORPHAN

class MemoryEngine:
    def __init__(self):
        self.active_traces: Dict[str, InteractionTrace] = {}
        self.working_memory: List[InteractionTrace] = []

    async def ingest_stimulus(self, payload: Dict[str, Any]) -> str:
        trace = InteractionTrace(stimulus=payload)
        self.active_traces[trace.trace_id] = trace
        return trace.trace_id

    async def associate_reaction(self, trace_id: str, payload: Dict[str, Any]):
        if trace_id in self.active_traces:
            trace = self.active_traces[trace_id]
            trace.commit(payload)
            self.working_memory.append(trace)
            return True
        return False

    def cleanup_orphans(self, ttl_seconds: int = 300):
        now = time.time()
        for tid, trace in list(self.active_traces.items()):
            if trace.status == TraceStatus.PENDING and (now - trace.timestamp) > ttl_seconds:
                trace.mark_orphan()
                self.working_memory.append(trace)
                del self.active_traces[tid]
