# Generated from design/memory_router.md v1.13
import uuid
import json
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

from src.memory.storage import Hippocampus, clear_chroma_clients
from src.memory.working import WorkingMemory, WorkingMemoryItem
from src.memory.signals import SignalDecomposer
from src.memory.neocortex import Neocortex
from src.memory.room_detector import RoomDetector
from src.memory.vault_indexer import VaultIndexer

logger = logging.getLogger("GATEWAY.MEMORY.ROUTER")

class MemoryRouter:
    """
    ClawBrain Memory Central Router.
    P18: Working Memory and Hippocampus search paths are isolated by context_id.
    P34: Organized into semantic Rooms within sessions.
    P35: Integration of External Knowledge (Vault).
    """
    def __init__(self, db_dir: str = None, distill_threshold: int = 50, 
                 distill_url: str = None, distill_model: str = None, distill_provider: str = None,
                 enable_room_detection: bool = True,
                 enable_auto_scan: bool = True,
                 enable_auto_distill: bool = True):
        logger.info(f"[ROUTER] Initializing with db_dir={db_dir}")
        if db_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "data")
            
        self.db_dir = db_dir
        self.distill_threshold = distill_threshold
        self.enable_room_detection = enable_room_detection
        self.enable_auto_distill = enable_auto_distill
        self.enable_auto_scan = enable_auto_scan
        
        # Phase 34: Isolated internal client
        self.internal_client = httpx.AsyncClient(timeout=120.0, limits=httpx.Limits(max_connections=20))
        
        self.hippo = Hippocampus(db_dir=db_dir)
        self.neo = Neocortex(db_dir=db_dir, distill_url=distill_url, 
                             distill_model=distill_model, distill_provider=distill_provider,
                             client=self.internal_client)
        
        self.room_detector = RoomDetector(
            url=self.neo.distill_url,
            model=self.neo.distill_model,
            provider=self.neo.distill_provider,
            api_key=self.neo.api_key,
            client=self.internal_client
        )

        # P35: Vault Indexer
        self.vault_path = os.getenv("CLAWBRAIN_VAULT_PATH")
        self.vault_enabled = os.getenv("CLAWBRAIN_ENABLE_VAULT_SCAN", "true").lower() == "true"
        self.vault_indexer = None
        
        if self.vault_path and self.vault_enabled:
            logger.info(f"[ROUTER] Vault enabled: {self.vault_path}")
            self.vault_indexer = VaultIndexer(self.vault_path, Path(db_dir), self.hippo.client)
            if self.enable_auto_scan:
                asyncio.create_task(self._vault_scan_loop())
        
        self._wm_sessions: Dict[str, WorkingMemory] = {}
        self._current_rooms: Dict[str, str] = {}
        self._known_rooms: Dict[str, set] = {}
        self.decomposer = SignalDecomposer()
        self._trace_counters: Dict[str, int] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}
        
        self._hydrate()

    async def aclose(self):
        await self.internal_client.aclose()

    def _get_current_room(self, session_id: str) -> str:
        return self._current_rooms.get(session_id, "general")

    def _get_known_rooms(self, session_id: str) -> List[str]:
        return list(self._known_rooms.get(session_id, {"general"}))

    def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        sid = session_id or "default"
        if sid not in self._session_locks:
            self._session_locks[sid] = asyncio.Lock()
        return self._session_locks[sid]

    def _get_wm(self, context_id: str) -> WorkingMemory:
        if context_id not in self._wm_sessions:
            self._wm_sessions[context_id] = WorkingMemory()
        return self._wm_sessions[context_id]

    def _hydrate(self):
        try:
            sessions = self.hippo.get_all_session_ids()
            for session in sessions:
                snapshot = self.hippo.load_wm_state(session)
                if snapshot:
                    wm = self._get_wm(session)
                    for row in snapshot:
                        item = WorkingMemoryItem(trace_id=row["trace_id"], content=row["content"], timestamp=row["timestamp"])
                        item.activation = row["activation"]
                        wm.items.append(item)
                    continue
                recent = self.hippo.get_recent_traces(limit=15, context_id=session)
                wm = self._get_wm(session)
                for row in reversed(recent):
                    content_json = row.get("raw_content") or self.hippo.get_content(row["trace_id"])
                    if content_json:
                        try:
                            payload = json.loads(content_json).get("stimulus", {})
                            intent = self.decomposer.extract_core_intent(payload)
                            wm.add_item(row["trace_id"], intent)
                        except: pass
        except Exception as e:
            logger.exception(f"Hydration failed: {e}")

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None,
                     offload_threshold: int = None, context_id: str = "default",
                     sync_distill: bool = False) -> str:
        trace_id = str(uuid.uuid4())
        intent = ""
        
        # 1. CORE WRITE (Locked)
        async with self._get_session_lock(context_id):
            intent = self.decomposer.extract_core_intent(payload)
            room_id = self._get_current_room(context_id)
            res = self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction},
                                        search_text=intent, threshold=offload_threshold,
                                        context_id=context_id, room_id=room_id)
            wm = self._get_wm(context_id)
            wm.add_item(trace_id, intent)
            self.hippo.save_wm_state(context_id, wm.items)
            
            if context_id not in self._trace_counters:
                self._trace_counters[context_id] = 0
            self._trace_counters[context_id] += 1

        # 2. COGNITIVE TASKS (Outside primary lock to avoid deadlocks)
        if sync_distill:
            if self.enable_room_detection:
                await self._perform_room_detection(context_id, intent)
            if self._trace_counters.get(context_id, 0) >= self.distill_threshold:
                self._trace_counters[context_id] = 0
                await self._perform_distillation(context_id)
        else:
            if self.enable_room_detection:
                asyncio.create_task(self._perform_room_detection(context_id, intent))
            if self._trace_counters.get(context_id, 0) >= self.distill_threshold:
                self._trace_counters[context_id] = 0
                if self.enable_auto_distill:
                    asyncio.create_task(self._perform_distillation(context_id))
        return trace_id

    async def _perform_room_detection(self, session_id: str, current_intent: str):
        try:
            history = []
            async with self._get_session_lock(session_id):
                wm = self._get_wm(session_id)
                history = wm.get_active_contents()
                known = self._get_known_rooms(session_id)

            new_room = await self.room_detector.detect_room(history, current_intent, known)

            # Update room status (Quick lock)
            async with self._get_session_lock(session_id):

                if new_room != self._get_current_room(session_id):
                    self._current_rooms[session_id] = new_room
                    if session_id not in self._known_rooms: self._known_rooms[session_id] = {"general"}
                    self._known_rooms[session_id].add(new_room)
        except Exception as e: logger.error(f"[ROOM_DET_FAIL] {e}")

    async def _perform_distillation(self, context_id: str):
        try:
            traces = self.hippo.get_recent_traces(limit=self.distill_threshold, context_id=context_id)
            if traces: await self.neo.distill(context_id, traces)
        except Exception as e: logger.error(f"[NC_DIST_FAIL] {e}")

    async def _vault_scan_loop(self):
        interval = int(os.getenv("CLAWBRAIN_VAULT_SCAN_INTERVAL", "300"))
        while True:
            try:
                if self.vault_indexer: await self.vault_indexer.scan()
            except: pass
            await asyncio.sleep(interval)

    async def get_combined_context(self, context_id: str, current_focus: str, max_chars: int = None) -> str:
        async with self._get_session_lock(context_id):
            budget = max_chars if max_chars is not None else int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", "2000"))
            remaining = budget - 50
            header_l3 = "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ==="
            header_v1 = "=== EXTERNAL KNOWLEDGE (VAULT) ==="
            header_l1 = "=== ACTIVE CONVERSATION (WORKING MEMORY) ==="
            header_l2 = "=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ==="

            # L3
            summary_raw = self.neo.get_summary(context_id)
            summary_text = ""
            if summary_raw:
                remaining -= len(header_l3) + 2
                summary_text = summary_raw[:int(budget * 0.4)]
                remaining -= len(summary_text)

            # Vault
            vault_text = ""
            if self.vault_indexer and remaining > 200:
                try:
                    v_res = self.vault_indexer.collection.query(query_texts=[current_focus], n_results=3)
                    if v_res and v_res["documents"] and v_res["documents"][0]:
                        v_parts = [f"- {d.strip()}" for d in v_res["documents"][0]]
                        cand = "\n".join(v_parts)
                        if len(header_v1) + len(cand) + 10 < remaining:
                            vault_text = cand
                            remaining -= (len(header_v1) + len(vault_text) + 2)
                except: pass

            # L1
            wm = self._get_wm(context_id)
            active = wm.get_active_contents()
            wm_text = ""
            if active:
                cand_wm = "\n".join(active)
                if len(header_l1) + len(cand_wm) + 2 > remaining:
                    avail = remaining - len(header_l1) - 2
                    wm_text = cand_wm[:avail] + "..." if avail > 20 else ""
                else: wm_text = cand_wm
                if wm_text: remaining -= (len(header_l1) + len(wm_text) + 2)

            # L2
            recalled = []
            if remaining > (len(header_l2) + 50):
                rem_l2 = remaining - (len(header_l2) + 2)
                ids = self.hippo.search(current_focus, context_id=context_id, room_id=self._get_current_room(context_id))
                if len(ids) < 3:
                    for gid in self.hippo.search(current_focus, context_id=context_id):
                        if gid not in ids: ids.append(gid)
                for tid in ids:
                    if rem_l2 <= 10: break
                    raw = self.hippo.get_content(tid)
                    if raw:
                        try:
                            data = json.loads(raw)
                            msg = data.get("stimulus", {}).get("messages", [{}])[0].get("content", "") or data.get("stimulus", {}).get("content", "")
                            fmt = f"- {msg}"
                            if len(fmt) > rem_l2:
                                if rem_l2 > 20: recalled.append(fmt[:rem_l2-3] + "..."); rem_l2 = 0
                                break
                            recalled.append(fmt); rem_l2 -= len(fmt)
                        except: pass

            # Assembly
            parts = []
            if summary_text: parts.extend([header_l3, summary_text])
            if vault_text:
                if parts: parts.append("")
                parts.extend([header_v1, vault_text])
            if wm_text:
                if parts: parts.append("")
                parts.extend([header_l1, wm_text])
            if recalled:
                if parts: parts.append("")
                parts.append(header_l2); parts.extend(recalled)
            
            if not parts: return ""
            return f"[CLAWBRAIN MEMORY]\n" + "\n".join(parts) + "\n[END CLAWBRAIN MEMORY]"
