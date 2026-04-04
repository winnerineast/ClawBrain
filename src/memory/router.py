# Generated from design/memory_router.md v1.0
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
        self.hippo = Hippocampus(db_dir=db_dir)
        self.wm = WorkingMemory()
        self.neo = Neocortex(db_dir=db_dir)
        self.decomposer = SignalDecomposer()

    async def ingest(self, payload: Dict[str, Any]) -> str:
        """
        2.1 准则：统一摄入逻辑
        """
        trace_id = str(uuid.uuid4())
        intent = self.decomposer.extract_core_intent(payload)
        
        # 1. 写入海马体 (L2)
        self.hippo.save_trace(trace_id, payload, search_text=intent)
        
        # 2. 写入工作记忆 (L1)
        self.wm.add_item(trace_id, intent)
        
        return trace_id

    async def get_combined_context(self, context_id: str, current_focus: str) -> str:
        """
        2.1 准则：复合上下文合成
        """
        # 1. 获取新皮层摘要 (L3)
        summary = self.neo.get_summary(context_id) or "No historical summary available."
        
        # 2. 获取海马体召回 (L2)
        search_hits = self.hippo.search(current_focus)
        
        # 3. 获取工作记忆活跃内容 (L1)
        active_msgs = self.wm.get_active_contents()
        
        # 按照“漏斗模型”组装
        context = [
            "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===",
            summary,
            "\n=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===",
            f"Hits found in {len(search_hits)} past interactions.",
            "\n=== ACTIVE CONVERSATION (WORKING MEMORY) ===",
            "\n".join(active_msgs)
        ]
        return "\n".join(context)
