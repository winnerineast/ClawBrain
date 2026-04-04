# Generated from design/memory.md v1.7
import time
import uuid
from enum import Enum
from typing import Dict, Any, Optional, List

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
        self.metadata = {}

    def commit(self, reaction: Dict[str, Any]):
        self.reaction = reaction
        self.status = TraceStatus.COMMITTED

    def mark_orphan(self):
        self.status = TraceStatus.ORPHAN

class MemoryEngine:
    def __init__(self):
        self.active_traces: Dict[str, InteractionTrace] = {}
        # 模拟工作记忆
        self.working_memory: List[InteractionTrace] = []

    async def ingest_stimulus(self, payload: Dict[str, Any]) -> str:
        """两阶段提交：第一步，记录输入"""
        trace = InteractionTrace(stimulus=payload)
        self.active_traces[trace.trace_id] = trace
        return trace.trace_id

    async def associate_reaction(self, trace_id: str, payload: Dict[str, Any]):
        """两阶段提交：第二步，关联响应并固化"""
        if trace_id in self.active_traces:
            trace = self.active_traces[trace_id]
            trace.commit(payload)
            self.working_memory.append(trace)
            # 这里未来会调用 storage.py 进行持久化
            return True
        return False

    def cleanup_orphans(self, ttl_seconds: int = 300):
        """处理孤儿输入：标记超时的 PENDING 记录"""
        now = time.time()
        for tid, trace in list(self.active_traces.items()):
            if trace.status == TraceStatus.PENDING and (now - trace.timestamp) > ttl_seconds:
                trace.mark_orphan()
                # 即使是孤儿也要移入工作记忆以供下一次“感知”
                self.working_memory.append(trace)
                del self.active_traces[tid]
