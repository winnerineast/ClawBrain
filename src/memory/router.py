# Generated from design/memory_router.md v1.10
import uuid
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from src.memory.storage import Hippocampus
from src.memory.working import WorkingMemory
from src.memory.neocortex import Neocortex
from src.memory.signals import SignalDecomposer

logger = logging.getLogger("GATEWAY.MEMORY")

class MemoryRouter:
    """
    ClawBrain 记忆中枢路由器。
    协调三层记忆的统一摄入与复合检索。
    """
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
        """恢复最近注意力状态"""
        try:
            recent = self.hippo.get_recent_traces(limit=15)
            for row in reversed(recent):
                tid = row["trace_id"]
                content_json = row["raw_content"] or self.hippo.get_content(tid)
                if content_json:
                    try:
                        payload = json.loads(content_json).get("stimulus", {})
                        intent = self.decomposer.extract_core_intent(payload)
                        self.wm.add_item(tid, intent)
                    except: pass
        except Exception as e:
            logger.error(f"Hydration failed: {e}")

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None, offload_threshold: int = None) -> str:
        trace_id = str(uuid.uuid4())
        intent = self.decomposer.extract_core_intent(payload)
        
        # 1. 存储层
        res = self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, 
                                   search_text=intent, threshold=offload_threshold)
        logger.info(f"[HP_STOR] Action: {'BLOB' if res['is_blob'] else 'SQL'} | TraceID: {trace_id}")
        
        # 2. 工作记忆
        self.wm.add_item(trace_id, intent)
        
        # 3. 自动提纯触发
        self._trace_counter += 1
        if self._trace_counter >= self.distill_threshold:
            logger.info(f"[NC_DIST] Threshold Reached ({self.distill_threshold}) -> Spawning Worker.")
            asyncio.create_task(self._auto_distill_worker(payload.get("context_id", "default")))
            self._trace_counter = 0
            
        return trace_id

    async def _auto_distill_worker(self, context_id: str):
        """2.4 准则修正：补齐 JSON 解码逻辑，修复数据结构错配"""
        if self._distill_lock.locked(): return
        async with self._distill_lock:
            try:
                # 1. 获取最近素材（数据库行）
                rows = self.hippo.get_recent_traces(limit=self.distill_threshold)
                
                # 2. 核心修复：将 raw_content 解码为 Neocortex 可理解的对象
                traces = []
                for row in rows:
                    raw = row.get("raw_content") or self.hippo.get_content(row["trace_id"])
                    if raw:
                        try:
                            traces.append(json.loads(raw))
                        except: pass
                
                # 3. 执行 LLM 提炼
                if traces:
                    await self.neo.distill(context_id, traces)
                    logger.info(f"[NC_DIST] Distillation Complete for session: {context_id} (Traces: {len(traces)})")
                else:
                    logger.warning("[NC_DIST] No valid traces found for distillation.")
                    
            except Exception as e:
                logger.error(f"Distillation worker failed: {e}")

    async def get_combined_context(self, context_id: str, current_focus: str) -> str:
        """2.3 准则：召回真实原文内容"""
        summary = self.neo.get_summary(context_id) or "No historical summary."
        search_ids = self.hippo.search(current_focus)
        
        recalled_contents = []
        for tid in search_ids:
            raw = self.hippo.get_content(tid)
            if raw:
                try:
                    data = json.loads(raw)
                    stim = data.get("stimulus", {}).get("messages", [])
                    recalled_contents.append(json.dumps(stim))
                except:
                    recalled_contents.append(raw[:200])
        
        active_msgs = self.wm.get_active_contents()
        
        context = [
            "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===",
            summary,
            "\n=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===",
            "\n".join(recalled_contents) if recalled_contents else "None.",
            "\n=== ACTIVE CONVERSATION (WORKING MEMORY) ===",
            "\n".join(active_msgs)
        ]
        return "\n".join(context)
