# Generated from design/memory_router.md v1.11
import uuid
import json
import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
from src.memory.storage import Hippocampus
from src.memory.working import WorkingMemory, WorkingMemoryItem
from src.memory.neocortex import Neocortex
from src.memory.signals import SignalDecomposer

logger = logging.getLogger("GATEWAY.MEMORY")

class MemoryRouter:
    """
    ClawBrain 记忆中枢路由器。
    P18: 工作记忆与海马体搜索全路径按 context_id 隔离。
    """
    def __init__(self, db_dir: str = "/home/nvidia/ClawBrain/data", distill_threshold: int = 50):
        self.db_dir = db_dir
        self.distill_threshold = distill_threshold
        self.hippo = Hippocampus(db_dir=db_dir)
        self.neo = Neocortex(db_dir=db_dir)
        self._wm_sessions: Dict[str, WorkingMemory] = {}   # P18: 按 session 隔离
        self.decomposer = SignalDecomposer()

        self._trace_counter = 0
        self._distill_lock = asyncio.Lock()
        self._hydrate()

    def _get_wm(self, context_id: str) -> WorkingMemory:
        """按需创建并缓存每个 session 的 WorkingMemory 实例"""
        if context_id not in self._wm_sessions:
            self._wm_sessions[context_id] = WorkingMemory()
        return self._wm_sessions[context_id]

    def _hydrate(self):
        """按 session 分别恢复工作记忆（P22: 优先从 wm_state 精确恢复）"""
        try:
            sessions = self.hippo.get_all_session_ids()
            for session in sessions:
                # P22: 优先从精确快照恢复（保留 activation + timestamp）
                snapshot = self.hippo.load_wm_state(session)
                if snapshot:
                    wm = self._get_wm(session)
                    for row in snapshot:
                        item = WorkingMemoryItem(
                            trace_id=row["trace_id"],
                            content=row["content"],
                            timestamp=row["timestamp"]
                        )
                        item.activation = row["activation"]
                        wm.items.append(item)
                    logger.info(f"[WM_HYDRATE] Exact restore: session={session} items={len(snapshot)}")
                    continue

                # 降级：从 traces 重建（旧行为）
                recent = self.hippo.get_recent_traces(limit=15, context_id=session)
                wm = self._get_wm(session)
                for row in reversed(recent):
                    content_json = row.get("raw_content") or self.hippo.get_content(row["trace_id"])
                    if content_json:
                        try:
                            payload = json.loads(content_json).get("stimulus", {})
                            intent = self.decomposer.extract_core_intent(payload)
                            wm.add_item(row["trace_id"], intent)
                        except:
                            pass
                logger.info(f"[WM_HYDRATE] Fallback rebuild: session={session} items={len(recent)}")
        except Exception as e:
            logger.error(f"Hydration failed: {e}")

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None,
                     offload_threshold: int = None, context_id: str = "default") -> str:
        trace_id = str(uuid.uuid4())
        intent = self.decomposer.extract_core_intent(payload)

        # 存储层：携带 context_id
        res = self.hippo.save_trace(
            trace_id,
            {"stimulus": payload, "reaction": reaction},
            search_text=intent,
            threshold=offload_threshold,
            context_id=context_id
        )
        logger.info(f"[HP_STOR] Action: {'BLOB' if res['is_blob'] else 'SQL'} | TraceID: {trace_id} | Session: {context_id}")

        # 工作记忆：写入对应 session 的 WM，并持久化快照（P22）
        wm = self._get_wm(context_id)
        wm.add_item(trace_id, intent)
        self.hippo.save_wm_state(context_id, wm.items)

        # 自动提纯触发
        self._trace_counter += 1
        if self._trace_counter >= self.distill_threshold:
            logger.info(f"[NC_DIST] Threshold Reached ({self.distill_threshold}) -> Spawning Worker.")
            asyncio.create_task(self._auto_distill_worker(context_id))
            self._trace_counter = 0

        return trace_id

    async def _auto_distill_worker(self, context_id: str):
        if self._distill_lock.locked():
            return
        async with self._distill_lock:
            try:
                rows = self.hippo.get_recent_traces(limit=self.distill_threshold, context_id=context_id)
                traces = []
                for row in rows:
                    raw = row.get("raw_content") or self.hippo.get_content(row["trace_id"])
                    if raw:
                        try:
                            traces.append(json.loads(raw))
                        except:
                            pass
                if traces:
                    await self.neo.distill(context_id, traces)
                    logger.info(f"[NC_DIST] Distillation Complete for session: {context_id} (Traces: {len(traces)})")
                else:
                    logger.warning("[NC_DIST] No valid traces found for distillation.")
            except Exception as e:
                logger.error(f"Distillation worker failed: {e}")

    async def get_combined_context(self, context_id: str, current_focus: str) -> str:
        """
        优先级贪心 Context 预算，全路径按 context_id 隔离 (P15 + P18)。
        分配顺序：L3 新皮层 → L2 海马体 → L1 工作记忆。
        """
        budget = int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", "2000"))
        remaining = budget

        # L3: 新皮层摘要
        summary_raw = self.neo.get_summary(context_id) or "No historical summary."
        if len(summary_raw) > remaining:
            summary_text = summary_raw[:remaining] + "..."
            remaining = 0
        else:
            summary_text = summary_raw
            remaining -= len(summary_text)

        # L2: 海马体语义召回（按 session 过滤）
        search_ids = self.hippo.search(current_focus, context_id=context_id)
        recalled_contents = []
        l2_used = 0
        for tid in search_ids:
            if remaining <= 0:
                break
            raw = self.hippo.get_content(tid)
            if raw:
                try:
                    data = json.loads(raw)
                    stim = data.get("stimulus", {}).get("messages", [])
                    content = json.dumps(stim, ensure_ascii=False)
                except:
                    content = raw[:200]
                if len(content) <= remaining:
                    recalled_contents.append(content)
                    remaining -= len(content)
                    l2_used += len(content)

        # L1: 工作记忆（按 session 隔离）
        active_msgs = self._get_wm(context_id).get_active_contents()
        active_raw = "\n".join(active_msgs)
        if len(active_raw) > remaining:
            active_text = active_raw[:remaining] + "..."
        else:
            active_text = active_raw
        l1_used = len(active_text)

        logger.info(
            f"[CTX_BUDGET] Budget: {budget} | "
            f"Used(L3): {len(summary_text)} | "
            f"Used(L2): {l2_used} | "
            f"Used(L1): {l1_used} | "
            f"Session: {context_id}"
        )

        context = [
            "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===",
            summary_text,
            "\n=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===",
            "\n".join(recalled_contents) if recalled_contents else "None.",
            "\n=== ACTIVE CONVERSATION (WORKING MEMORY) ===",
            active_text
        ]
        return "\n".join(context)
