# Generated from design/memory_router.md v1.11
import uuid
import json
import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
from src.memory.storage import Hippocampus, clear_chroma_clients
from src.memory.working import WorkingMemory, WorkingMemoryItem
from src.memory.signals import SignalDecomposer
from src.memory.neocortex import Neocortex
from src.memory.room_detector import RoomDetector

logger = logging.getLogger("GATEWAY.MEMORY.ROUTER")

class MemoryRouter:
    """
    ClawBrain Memory Central Router.
    P18: Working Memory and Hippocampus search paths are isolated by context_id.
    P34: Organized into semantic Rooms within sessions.
    """
    def __init__(self, db_dir: str = None, distill_threshold: int = 50, 
                 distill_url: str = None, distill_model: str = None, distill_provider: str = None,
                 enable_room_detection: bool = True):
        logger.info(f"[ROUTER] Initializing with db_dir={db_dir}")
        if db_dir is None:
            # Dynamic default path for portability (Issue-003)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "data")
            
        self.db_dir = db_dir
        self.distill_threshold = distill_threshold
        self.enable_room_detection = enable_room_detection
        
        # Phase 34: Isolated internal client for background awareness (NC_DIST, ROOM_DET)
        import httpx
        self.internal_client = httpx.AsyncClient(timeout=60.0, limits=httpx.Limits(max_connections=20))
        
        logger.info("[ROUTER] Creating Hippocampus...")
        self.hippo = Hippocampus(db_dir=db_dir)
        
        logger.info("[ROUTER] Creating Neocortex...")
        self.neo = Neocortex(db_dir=db_dir, distill_url=distill_url, 
                             distill_model=distill_model, distill_provider=distill_provider,
                             client=self.internal_client)
        
        # P34: Room Detector
        self.room_detector = RoomDetector(
            url=self.neo.distill_url,
            model=self.neo.distill_model,
            provider=self.neo.distill_provider,
            api_key=self.neo.api_key,
            client=self.internal_client
        )
        
        self._wm_sessions: Dict[str, WorkingMemory] = {}   # P18: Isolated by session
        self._current_rooms: Dict[str, str] = {}           # P34: Current room per session
        self._known_rooms: Dict[str, set] = {}             # P34: Set of known rooms per session
        
        self.decomposer = SignalDecomposer()

        self._trace_counters: Dict[str, int] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {} # Phase 32: Per-session serialization
        
        logger.info("[ROUTER] Starting Hydration...")
        self._hydrate()
        logger.info("[ROUTER] Initialization complete.")

    async def aclose(self):
        """Phase 34: Close internal cognitive plane client."""
        await self.internal_client.aclose()
        logger.info("[ROUTER] Internal client closed.")

    def _get_current_room(self, session_id: str) -> str:
        return self._current_rooms.get(session_id, "general")

    def _get_known_rooms(self, session_id: str) -> List[str]:
        return list(self._known_rooms.get(session_id, {"general"}))

    def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        """Lazily create session lock."""
        sid = session_id or "default"
        if sid not in self._session_locks:
            self._session_locks[sid] = asyncio.Lock()
        return self._session_locks[sid]

    def _get_wm(self, context_id: str) -> WorkingMemory:
        """Create and cache WorkingMemory instances per session on demand."""
        if context_id not in self._wm_sessions:
            self._wm_sessions[context_id] = WorkingMemory()
        return self._wm_sessions[context_id]

    def _hydrate(self):
        """Restore working memory per session (P22: Priority to exact restore from wm_state)."""
        logger.info("[ROUTER.HYDRATE] Fetching all session IDs...")
        try:
            sessions = self.hippo.get_all_session_ids()
            logger.info(f"[ROUTER.HYDRATE] Found {len(sessions)} sessions.")
            for session in sessions:
                # P22: Priority restore from exact snapshot (preserves activation + timestamp)
                logger.info(f"[ROUTER.HYDRATE] Processing session: {session}")
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
                logger.info(f"[ROUTER.HYDRATE] Fallback: Fetching recent traces for session: {session}")
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
            logger.exception(f"Hydration failed: {e}")

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None,
                     offload_threshold: int = None, context_id: str = "default",
                     sync_distill: bool = False) -> str:
        """Phase 32: Asynchronous Sequential Gate."""
        async with self._get_session_lock(context_id):
            trace_id = str(uuid.uuid4())
            intent = self.decomposer.extract_core_intent(payload)
            
            # P34: Asynchronous Room Detection
            room_id = self._get_current_room(context_id)
            if self.enable_room_detection:
                # Trigger background room detection for NEXT turn
                asyncio.create_task(self._update_room_async(context_id, intent))

            # Storage layer: include context_id and room_id
            res = self.hippo.save_trace(
                trace_id,
                {"stimulus": payload, "reaction": reaction},
                search_text=intent,
                threshold=offload_threshold,
                context_id=context_id,
                room_id=room_id
            )
            logger.info(f"[HP_STOR] Action: {'BLOB' if res['is_blob'] else 'CHROMA'} | TraceID: {trace_id} | Session: {context_id} | Room: {room_id}")

            # Working Memory: Write to session WM and persist snapshot (P22)
            wm = self._get_wm(context_id)
            wm.add_item(trace_id, intent)
            self.hippo.save_wm_state(context_id, wm.items)

            # P29: Automatic Distillation Trigger
            if context_id not in self._trace_counters:
                self._trace_counters[context_id] = 0
            
            self._trace_counters[context_id] += 1
            if self._trace_counters[context_id] >= self.distill_threshold:
                self._trace_counters[context_id] = 0
                if sync_distill:
                    await self._auto_distill_worker(context_id)
                else:
                    asyncio.create_task(self._auto_distill_worker(context_id))

            return trace_id

    async def _update_room_async(self, session_id: str, current_intent: str):
        """Phase 34: Background task to detect topic shifts."""
        try:
            wm = self._get_wm(session_id)
            history = wm.get_active_contents()
            known = self._get_known_rooms(session_id)
            
            new_room = await self.room_detector.detect_room(history, current_intent, known)
            
            if new_room != self._get_current_room(session_id):
                logger.info(f"[ROOM_SHIFT] Session {session_id} moved to Room: {new_room}")
                self._current_rooms[session_id] = new_room
                if session_id not in self._known_rooms:
                    self._known_rooms[session_id] = {"general"}
                self._known_rooms[session_id].add(new_room)
        except Exception as e:
            logger.error(f"[ROOM_UPDATE_FAIL] {e}")

    async def get_combined_context(self, context_id: str, current_focus: str, max_chars: int = None) -> str:
        """Phase 32: Protected Context Assembly. P34: Room-Prioritized Search."""
        async with self._get_session_lock(context_id):
            budget = max_chars if max_chars is not None else int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", "2000"))
            
            # Subract outer wrapper length upfront (~45 chars)
            remaining = budget - 50
            
            # Headers
            header_l3 = "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ==="
            header_l1 = "=== ACTIVE CONVERSATION (WORKING MEMORY) ==="
            header_l2 = "=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ==="

            # L3: Neocortex Summary (Phase 29: Only inject if exists)
            summary_raw = self.neo.get_summary(context_id)
            summary_text = ""
            if summary_raw:
                # Account for L3 header
                remaining -= len(header_l3) + 2
                summary_text = summary_raw
                # Heuristic: limit L3 to 40% of initial budget if other layers might exist
                limit_l3 = int(budget * 0.4)
                if len(summary_text) > limit_l3:
                    summary_text = summary_text[:limit_l3] + "..."
                remaining -= len(summary_text)

            # L1: Working Memory (Highest precision)
            wm = self._get_wm(context_id)
            active_contents = wm.get_active_contents()
            wm_text = ""
            if active_contents:
                # Account for L1 header
                remaining -= len(header_l1) + 2
                wm_text = "\n".join(active_contents)
                # Budget check
                if len(wm_text) > remaining:
                    wm_text = wm_text[:max(0, remaining)] + "..."
                remaining -= len(wm_text)

            # L2: Hippocampus (Semantic Recall)
            # P34: Priority to current room
            current_room = self._get_current_room(context_id)
            recalled_contents = []
            
            # Only proceed if we have meaningful space left for L2 header + at least one snippet
            if remaining > (len(header_l2) + 50):
                remaining -= len(header_l2) + 2
                
                # Phase 1: Room-Locked Search
                search_ids = self.hippo.search(current_focus, context_id=context_id, room_id=current_room)
                
                # Phase 2: Fallback to Global Session Search if low results
                if len(search_ids) < 3:
                    global_ids = self.hippo.search(current_focus, context_id=context_id)
                    # Merge and deduplicate
                    for gid in global_ids:
                        if gid not in search_ids:
                            search_ids.append(gid)

                for tid in search_ids:
                    if remaining <= 10: break
                    raw = self.hippo.get_content(tid)
                    if raw:
                        try:
                            data = json.loads(raw)
                            # P30: Format as plain text bullet point
                            msg = data.get("stimulus", {}).get("messages", [{}])[0].get("content", "")
                            if not msg:
                                msg = data.get("stimulus", {}).get("content", "")
                            
                            formatted = f"- {msg}"
                            if len(formatted) > remaining:
                                # Don't add partial bullets if they are too short
                                if remaining > 20:
                                    formatted = formatted[:remaining-3] + "..."
                                    recalled_contents.append(formatted)
                                    remaining = 0
                                break
                            
                            recalled_contents.append(formatted)
                            remaining -= len(formatted)
                        except:
                            pass
            
            total_used = budget - max(0, remaining)

            # Final Dynamic assembly with rigid budget enforcement
            parts = []
            current_len = 50 # Base for [CLAWBRAIN MEMORY] wrapper
            
            if summary_text:
                parts.append(header_l3)
                parts.append(summary_text)
                current_len += len(header_l3) + len(summary_text) + 2
            
            if wm_text:
                candidate_header = "\n" + header_l1 if parts else header_l1
                # Only add if it actually fits and adds value
                if current_len + len(candidate_header) + 10 < budget:
                    parts.append("") if parts else None
                    parts.append(header_l1)
                    # Fit what we can of WM
                    available = budget - current_len - len(candidate_header) - 1
                    if len(wm_text) > available:
                        wm_text = wm_text[:max(0, available-3)] + "..."
                    parts.append(wm_text)
                    current_len += len(candidate_header) + len(wm_text) + 1
            
            if recalled_contents:
                candidate_header = "\n" + header_l2 if parts else header_l2
                # Only add if it actually fits and adds value
                if current_len + len(candidate_header) + 20 < budget:
                    parts.append("") if parts else None
                    parts.append(header_l2)
                    current_len += len(candidate_header) + 1
                    for snippet in recalled_contents:
                        if current_len + len(snippet) + 1 < budget:
                            parts.append(snippet)
                            current_len += len(snippet) + 1
                        else:
                            # Try a partial snippet as last resort
                            available = budget - current_len - 1
                            if available > 20:
                                parts.append(snippet[:available-3] + "...")
                            break

            if not parts:
                return ""
                
            combined = "\n".join(parts)
            # Hard crop safety
            final_str = f"[CLAWBRAIN MEMORY]\n{combined}\n[END CLAWBRAIN MEMORY]"
            return final_str[:budget]

    async def _auto_distill_worker(self, context_id: str):
        """Phase 29: Background worker for semantic fact distillation."""
        try:
            logger.info(f"[NC_DIST] Triggered for session: {context_id}")
            # 1. Fetch recent traces (exclude blobs if too large)
            traces = self.hippo.get_recent_traces(limit=self.distill_threshold, context_id=context_id)
            if traces:
                summary = await self.neo.distill(context_id, traces)
                logger.info(f"[NC_DIST] Summary updated for {context_id}")
            else:
                logger.warning("[NC_DIST] No valid traces found for distillation.")
        except Exception as e:
            logger.error(f"[NC_DIST] Worker failed: {e}")
