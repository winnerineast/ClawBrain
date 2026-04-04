# Generated from design/memory_router.md v1.8
import uuid
import json
import asyncio
from typing import Dict, Any, List
from src.memory.storage import Hippocampus
from src.memory.working import WorkingMemory
from src.memory.neocortex import Neocortex
from src.memory.signals import SignalDecomposer

class MemoryRouter:
    """
    ClawBrain 记忆中枢路由器。
    实现基于‘语义整合周期’的自适应提纯逻辑。
    """
    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data", distill_threshold: int = 50):
        # 2.1 准则：定义语义整合周期
        self.db_dir = db_dir
        self.distill_threshold = distill_threshold
        self.hippo = Hippocampus(db_dir=db_dir)
        self.neo = Neocortex(db_dir=db_dir)
        self.wm = WorkingMemory()
        self.decomposer = SignalDecomposer()
        
        self._trace_counter = 0
        self._distill_lock = asyncio.Lock()

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None, offload_threshold: int = None) -> str:
        trace_id = str(uuid.uuid4())
        intent = self.decomposer.extract_core_intent(payload)
        
        # 1. 动态分流持久化 (2.2 准则)
        self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, 
                             search_text=intent, threshold=offload_threshold)
        
        # 2. 工作记忆激活
        self.wm.add_item(trace_id, intent)
        
        # 3. 认知负荷检查与自适应提纯 (2.3 准则)
        self._trace_counter += 1
        if self._trace_counter >= self.distill_threshold:
            print(f"[MEMORY_DYNAMIC] Cognitive Load Reached ({self.distill_threshold}) -> Triggering Consolidation Epoch.")
            asyncio.create_task(self._auto_distill_worker(payload.get("context_id", "default")))
            self._trace_counter = 0
            
        return trace_id

    async def _auto_distill_worker(self, context_id: str):
        if self._distill_lock.locked(): return
        async with self._distill_lock:
            # 整合逻辑占位
            pass

    async def get_combined_context(self, context_id: str, current_focus: str) -> str:
        summary = self.neo.get_summary(context_id) or "No historical summary."
        search_hits = self.hippo.search(current_focus)
        active_msgs = self.wm.get_active_contents()
        return f"SUMMARY: {summary}\nRECALL: {search_hits}\nACTIVE: {active_msgs}"
