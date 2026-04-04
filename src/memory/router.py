# Generated from design/memory_integration.md v1.2
import uuid
import sqlite3
import json
import asyncio
from typing import Dict, Any, List, Optional
from src.memory.storage import Hippocampus
from src.memory.working import WorkingMemory
from src.memory.neocortex import Neocortex
from src.memory.signals import SignalDecomposer

class MemoryRouter:
    """
    ClawBrain 记忆中枢路由器。
    协调三层记忆的统一摄入与复合检索，并支持状态持久化恢复。
    """
    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data", distill_threshold: int = 50):
        # 2.1 准则：自洽初始化
        self.db_dir = db_dir
        self.distill_threshold = distill_threshold
        self.hippo = Hippocampus(db_dir=db_dir)
        self.neo = Neocortex(db_dir=db_dir)
        self.wm = WorkingMemory()
        self.decomposer = SignalDecomposer()
        
        self._trace_counter = 0
        self._distill_lock = asyncio.Lock()
        
        # 2.1 准则：启动时状态恢复 (Hydration)
        self._hydrate()

    def _hydrate(self):
        """从海马体恢复最近对话注意力"""
        try:
            with sqlite3.connect(self.hippo.db_path) as conn:
                cursor = conn.execute(
                    "SELECT trace_id, raw_content FROM traces ORDER BY timestamp DESC LIMIT 15"
                )
                rows = cursor.fetchall()
                for tid, content_json in reversed(rows):
                    if content_json:
                        try:
                            payload = json.loads(content_json)
                            # 提取原始 Stimulus 意图
                            stimulus = payload.get("stimulus", {})
                            intent = self.decomposer.extract_core_intent(stimulus)
                            self.wm.add_item(tid, intent)
                        except: pass
        except: pass

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None, offload_threshold: int = None) -> str:
        """
        2.1 准则：支持对称摄入与动态分流
        """
        trace_id = str(uuid.uuid4())
        intent = self.decomposer.extract_core_intent(payload)
        
        # 1. 持久化 (支持动态分流阈值)
        self.hippo.save_trace(
            trace_id, 
            {"stimulus": payload, "reaction": reaction}, 
            search_text=intent,
            threshold=offload_threshold
        )
        
        # 2. 激活工作记忆
        self.wm.add_item(trace_id, intent)
        
        # 3. 自动整合触发
        self._trace_counter += 1
        if self._trace_counter >= self.distill_threshold:
            asyncio.create_task(self._auto_distill_worker(payload.get("context_id", "default")))
            self._trace_counter = 0
            
        return trace_id

    async def _auto_distill_worker(self, context_id: str):
        if self._distill_lock.locked(): return
        async with self._distill_lock:
            # 此处预留后台提纯的具体调用逻辑
            pass

    async def get_combined_context(self, context_id: str, current_focus: str) -> str:
        """
        2.1 准则：三层记忆复合检索
        """
        summary = self.neo.get_summary(context_id) or "No historical summary."
        search_hits = self.hippo.search(current_focus)
        active_msgs = self.wm.get_active_contents()
        
        context = [
            "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===",
            summary,
            "\n=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===",
            f"Recall IDs: {search_hits}",
            "\n=== ACTIVE CONVERSATION (WORKING MEMORY) ===",
            "\n".join(active_msgs)
        ]
        return "\n".join(context)
