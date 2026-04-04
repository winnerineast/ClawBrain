# Generated from design/memory_router.md v1.6
import uuid
import sqlite3
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
    2.1 准则修复：显式传递路径，并新增自动提纯触发逻辑。
    """
    DISTILL_THRESHOLD = 50 # 每 50 条触发一次整合

    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data"):
        self.db_dir = db_dir
        self.hippo = Hippocampus(db_dir=db_dir)
        self.neo = Neocortex(db_dir=db_dir)
        self.wm = WorkingMemory()
        self.decomposer = SignalDecomposer()
        
        # 内部状态：Trace 计数器
        self._trace_counter = 0
        self._distill_lock = asyncio.Lock()
        
        self._hydrate()

    def _hydrate(self):
        try:
            with sqlite3.connect(self.hippo.db_path) as conn:
                cursor = conn.execute("SELECT trace_id, raw_content FROM traces ORDER BY timestamp DESC LIMIT 15")
                rows = cursor.fetchall()
                for tid, content_json in reversed(rows):
                    if content_json:
                        payload = json.loads(content_json).get("stimulus", {})
                        intent = self.decomposer.extract_core_intent(payload)
                        self.wm.add_item(tid, intent)
        except: pass

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None) -> str:
        trace_id = str(uuid.uuid4())
        intent = self.decomposer.extract_core_intent(payload)
        
        # 1. 持久化存储
        self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, search_text=intent)
        
        # 2. 工作记忆激活
        self.wm.add_item(trace_id, intent)
        
        # 3. 自动提纯触发 (2.1 准则)
        self._trace_counter += 1
        if self._trace_counter >= self.DISTILL_THRESHOLD:
            # 获取最近的会话 ID (context_id)
            context_id = payload.get("context_id", "default")
            # 异步启动新皮层整合任务
            asyncio.create_task(self._auto_distill_task(context_id))
            self._trace_counter = 0
            
        return trace_id

    async def _auto_distill_task(self, context_id: str):
        """后台异步任务：不阻塞主流程"""
        if self._distill_lock.locked():
            return
        
        async with self._distill_lock:
            print(f"[MEMORY_DYNAMIC] Threshold Reached ({self.DISTILL_THRESHOLD}) -> Spawning Neocortex Background Worker.")
            # 获取最近的 Trace 数据（简化：这里仅示意逻辑）
            # 实际会从海马体查询最近 50 条
            # await self.neo.distill(context_id, [...])
            pass

    async def get_combined_context(self, context_id: str, current_focus: str) -> str:
        summary = self.neo.get_summary(context_id) or "No historical summary available."
        search_hits = self.hippo.search(current_focus)
        active_msgs = self.wm.get_active_contents()
        
        context = [
            "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===",
            summary,
            "\n=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===",
            f"Recall Trace IDs: {search_hits}",
            "\n=== ACTIVE CONVERSATION (WORKING MEMORY) ===",
            "\n".join(active_msgs)
        ]
        return "\n".join(context)
