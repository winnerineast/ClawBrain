# Generated from design/memory_router.md v1.2
import uuid
from typing import Dict, Any, List
from src.memory.storage import Hippocampus
from src.memory.working import WorkingMemory
from src.memory.neocortex import Neocortex
from src.memory.signals import SignalDecomposer

class MemoryRouter:
    """
    ClawBrain 记忆中枢路由器。
    协调三层记忆的统一摄入与复合检索。
    """
    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data"):
        # 2.1 准则：显式传递 db_dir，确保路径一致性
        self.hippo = Hippocampus(db_dir=db_dir)
        self.neo = Neocortex(db_dir=db_dir)
        self.wm = WorkingMemory()
        self.decomposer = SignalDecomposer()

    async def ingest(self, payload: Dict[str, Any]) -> str:
        trace_id = str(uuid.uuid4())
        intent = self.decomposer.extract_core_intent(payload)
        
        # 1. 写入海马体 (L2) - 触发 FTS5 全文索引
        self.hippo.save_trace(trace_id, payload, search_text=intent)
        
        # 2. 写入工作记忆 (L1) - 触发活跃度更新
        self.wm.add_item(trace_id, intent)
        
        return trace_id

    async def get_combined_context(self, context_id: str, current_focus: str) -> str:
        summary = self.neo.get_summary(context_id) or "No historical summary available."
        search_hits = self.hippo.search(current_focus)
        active_msgs = self.wm.get_active_contents()
        
        context = [
            "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===",
            summary,
            "\n=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===",
            f"Trace IDs recalled: {search_hits}",
            "\n=== ACTIVE CONVERSATION (WORKING MEMORY) ===",
            "\n".join(active_msgs)
        ]
        return "\n".join(context)
