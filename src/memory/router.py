# Generated from design/gateway.md v1.28
import uuid
import sqlite3
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from src.memory.storage import Hippocampus
from src.memory.working import WorkingMemory
from src.memory.neocortex import Neocortex
from src.memory.signals import SignalDecomposer

# 2.4 准则修复：使用子 Logger 确保日志传播
logger = logging.getLogger("GATEWAY.MEMORY")

class MemoryRouter:
    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data", distill_threshold: int = 50):
        self.db_dir = db_dir
        self.distill_threshold = distill_threshold
        self.hippo = Hippocampus(db_dir=db_dir)
        self.neo = Neocortex(db_dir=db_dir)
        self.wm = WorkingMemory()
        self.decomposer = SignalDecomposer()
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
                        try:
                            payload = json.loads(content_json).get("stimulus", {})
                            intent = self.decomposer.extract_core_intent(payload)
                            self.wm.add_item(tid, intent)
                        except: pass
        except: pass

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None, offload_threshold: int = None) -> str:
        trace_id = str(uuid.uuid4())
        intent = self.decomposer.extract_core_intent(payload)
        
        # 1. 存储层
        res = self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, 
                                   search_text=intent, threshold=offload_threshold)
        
        # 2.4 埋点 [HP_STOR]
        storage_mode = "BLOB" if res["is_blob"] else "SQL"
        logger.info(f"[HP_STOR] Action: {storage_mode} | TraceID: {trace_id} | Size: {res['size']}")
        
        # 2. 工作记忆
        self.wm.add_item(trace_id, intent)
        
        # 3. 自动提纯
        self._trace_counter += 1
        if self._trace_counter >= self.distill_threshold:
            logger.info(f"[NC_DIST] Threshold Reached ({self.distill_threshold}) -> Triggering Consolidation.")
            asyncio.create_task(self._auto_distill_worker(payload.get("context_id", "default")))
            self._trace_counter = 0
            
        return trace_id

    async def _auto_distill_worker(self, context_id: str):
        if self._distill_lock.locked(): return
        async with self._distill_lock:
            pass

    async def get_combined_context(self, context_id: str, current_focus: str) -> str:
        summary = self.neo.get_summary(context_id) or "No historical summary."
        search_hits = self.hippo.search(current_focus)
        active_msgs = self.wm.get_active_contents()
        
        # 2.4 埋点 [WM_ACT]
        logger.info(f"[WM_ACT] Active Items: {len(active_msgs)} | Recall Hits: {len(search_hits)}")
        
        context = [
            "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===",
            summary,
            "\n=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===",
            f"Recall IDs: {search_hits}",
            "\n=== ACTIVE CONVERSATION (WORKING MEMORY) ===",
            "\n".join(active_msgs)
        ]
        return "\n".join(context)
