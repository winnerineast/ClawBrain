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
    ClawBrain Memory Central Router.
    P18: Working Memory and Hippocampus search paths are isolated by context_id.
    """
    def __init__(self, db_dir: str = None, distill_threshold: int = 50, 
                 distill_url: str = None, distill_model: str = None, distill_provider: str = None):
        if db_dir is None:
            # Dynamic default path for portability (Issue-003)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "data")
            
        self.db_dir = db_dir
        self.distill_threshold = distill_threshold
        self.hippo = Hippocampus(db_dir=db_dir)
        self.neo = Neocortex(db_dir=db_dir, distill_url=distill_url, 
                             distill_model=distill_model, distill_provider=distill_provider)
        self._wm_sessions: Dict[str, WorkingMemory] = {}   # P18: Isolated by session
        self.decomposer = SignalDecomposer()

        self._trace_counter = 0
        self._distill_lock = asyncio.Lock()
        self._hydrate()

    def _get_wm(self, context_id: str) -> WorkingMemory:
        """Create and cache WorkingMemory instances per session on demand."""
        if context_id not in self._wm_sessions:
            self._wm_sessions[context_id] = WorkingMemory()
        return self._wm_sessions[context_id]

    def _hydrate(self):
        """Restore working memory per session (P22: Priority to exact restore from wm_state)."""
        try:
            sessions = self.hippo.get_all_session_ids()
            for session in sessions:
                # P22: Priority restore from exact snapshot (preserves activation + timestamp)
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

                # Fallback: Rebuild from traces (Legacy behavior)
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

        # Storage layer: include context_id
        res = self.hippo.save_trace(
            trace_id,
            {"stimulus": payload, "reaction": reaction},
            search_text=intent,
            threshold=offload_threshold,
            context_id=context_id
        )
        logger.info(f"[HP_STOR] Action: {'BLOB' if res['is_blob'] else 'SQL'} | TraceID: {trace_id} | Session: {context_id}")

        # Working Memory: Write to session WM and persist snapshot (P22)
        wm = self._get_wm(context_id)
        wm.add_item(trace_id, intent)
        self.hippo.save_wm_state(context_id, wm.items)

        # Trigger auto-distillation
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
        Greedy Context Budgeting with session isolation (P15 + P18).
        Priority: L3 (Neocortex) -> L1 (Working Memory) -> L2 (Hippocampus). (Phase 31)
        """
        budget = int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", "2000"))
        remaining = budget

        # L3: Neocortex Summary (Phase 29: Only inject if exists)
        summary_raw = self.neo.get_summary(context_id)
        summary_text = ""
        if summary_raw:
            # L3 is highest priority, we take what we can, at least a header
            header_l3 = "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ==="
            if remaining > len(header_l3) + 20:
                remaining -= (len(header_l3) + 1)
                if len(summary_raw) > remaining:
                    summary_text = summary_raw[:remaining] + "..."
                    remaining = 0
                else:
                    summary_text = summary_raw
                    remaining -= len(summary_text)
            else:
                summary_raw = None # Not enough budget even for header

        # L1: Working Memory (Phase 31: Priority elevation)
        active_msgs = self._get_wm(context_id).get_active_contents()
        active_raw = "\n".join(active_msgs)
        active_text = ""
        l1_used = 0
        if active_raw:
            header_l1 = "=== ACTIVE CONVERSATION (WORKING MEMORY) ==="
            # Check if we have budget for header + some content (Phase 31 safety)
            if remaining > len(header_l1) + 20:
                remaining -= (len(header_l1) + 1)
                if len(active_raw) > remaining:
                    active_text = active_raw[:remaining] + "..."
                    l1_used = remaining
                    remaining = 0
                else:
                    active_text = active_raw
                    l1_used = len(active_text)
                    remaining -= l1_used

        # L2: Hippocampus Semantic Recall (Filtered by session)
        search_ids = self.hippo.search(current_focus, context_id=context_id)
        recalled_contents = []
        l2_used = 0
        if search_ids:
            header_l2 = "=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ==="
            if remaining > len(header_l2) + 20:
                header_budget_deducted = False
                for tid in search_ids:
                    if remaining <= 10: break
                    raw = self.hippo.get_content(tid)
                    if raw:
                        try:
                            data = json.loads(raw)
                            stim_msgs = data.get("stimulus", {}).get("messages", [])
                            lines = [f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in stim_msgs if m.get("content")]
                            content = " | ".join(lines)
                        except:
                            content = raw[:200]
                        
                        # Only add header once we have at least one snippet
                        if not header_budget_deducted:
                            remaining -= (len(header_l2) + 1)
                            header_budget_deducted = True

                        if len(content) + 2 <= remaining:
                            recalled_contents.append(f"- {content}")
                            remaining -= (len(content) + 2)
                            l2_used += (len(content) + 2)

        logger.info(
            f"[CTX_BUDGET] Budget: {budget} | "
            f"Used(L3): {len(summary_text)} | "
            f"Used(L1): {l1_used} | "
            f"Used(L2): {l2_used} | "
            f"Session: {context_id}"
        )

        # Dynamic assembly
        parts = []
        if summary_text:
            parts.append("=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===")
            parts.append(summary_text)

        if active_text:
            if parts: parts.append("")
            parts.append("=== ACTIVE CONVERSATION (WORKING MEMORY) ===")
            parts.append(active_text)
        
        if recalled_contents:
            if parts: parts.append("")
            parts.append("=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===")
            parts.extend(recalled_contents)

        return "\n".join(parts) if parts else ""
