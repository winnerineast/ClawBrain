# Generated from design/memory_integration.md v1.1
import uuid
import sqlite3
import json
from typing import Dict, Any, List
from src.memory.storage import Hippocampus
from src.memory.working import WorkingMemory
from src.memory.neocortex import Neocortex
from src.memory.signals import SignalDecomposer

class MemoryRouter:
    """
    ClawBrain 记忆中枢路由器。
    协调三层记忆的统一摄入与复合检索，并支持状态持久化恢复。
    """
    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data"):
        self.db_dir = db_dir
        self.hippo = Hippocampus(db_dir=db_dir)
        self.neo = Neocortex(db_dir=db_dir)
        self.wm = WorkingMemory()
        self.decomposer = SignalDecomposer()
        
        # 2.1 准则：系统启动时从海马体恢复工作记忆状态
        self._hydrate()

    def _hydrate(self):
        """从 SQLite 加载最近的 15 条记录进入工作记忆"""
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
                            # 如果是 InteractionTrace 格式，stimulus 在 key 里面
                            stimulus = payload.get("stimulus", payload)
                            intent = self.decomposer.extract_core_intent(stimulus)
                            self.wm.add_item(tid, intent)
                        except:
                            pass
        except Exception:
            pass

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None) -> str:
        """
        2.1 准则：支持同时接收刺激与反应
        """
        trace_id = str(uuid.uuid4())
        intent = self.decomposer.extract_core_intent(payload)
        
        # 写入海马体
        self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, search_text=intent)
        
        # 写入工作记忆
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
            f"Recall Trace IDs: {search_hits}",
            "\n=== ACTIVE CONVERSATION (WORKING MEMORY) ===",
            "\n".join(active_msgs)
        ]
        return "\n".join(context)
