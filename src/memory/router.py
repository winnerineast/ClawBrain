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
                 enable_auto_distill: bool = True,
                 vault_path: str = None):
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
        
        # State placeholders (initialized in background)
        self.hippo = None
        self.neo = None
        self.room_detector = None
        self.vault_indexer = None
        
        self.distill_url = distill_url
        self.distill_model = distill_model
        self.distill_provider = distill_provider

        # P35: Vault Config - Explicit param takes priority over ENV
        self.vault_path = vault_path or os.getenv("CLAWBRAIN_VAULT_PATH")
        self.vault_enabled = os.getenv("CLAWBRAIN_ENABLE_VAULT_SCAN", "true").lower() == "true"
        
        self._wm_sessions: Dict[str, WorkingMemory] = {}
        self._current_rooms: Dict[str, str] = {}
        self._known_rooms: Dict[str, set] = {}
        self.decomposer = SignalDecomposer()
        self._trace_counters: Dict[str, int] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}
        
        # Phase 36: Cognitive Plane Decoupling
        self.ready_event = asyncio.Event()
        asyncio.create_task(self._startup_routine())

    async def wait_until_ready(self, timeout: float = 60.0):
        """Wait for the cognitive plane to stabilize."""
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"[ROUTER] Engine failed to stabilize within {timeout}s")
            raise

    async def _startup_routine(self):
        """Self-paced cognitive initialization (Non-blocking)."""
        try:
            logger.info("[COGNITIVE] Establishing long-term memory engine...")
            
            # 1. Initialize Core Storage (ChromaDB connection happens here)
            self.hippo = Hippocampus(db_dir=self.db_dir)
            self.neo = Neocortex(db_dir=self.db_dir, distill_url=self.distill_url, 
                                 distill_model=self.distill_model, distill_provider=self.distill_provider,
                                 client=self.internal_client)
            
            self.room_detector = RoomDetector(
                url=self.neo.distill_url,
                model=self.neo.distill_model,
                provider=self.neo.distill_provider,
                api_key=self.neo.api_key,
                client=self.internal_client
            )

            # 2. Initialize Vault if enabled
            if self.vault_path and self.vault_enabled:
                logger.info(f"[COGNITIVE] Indexing Vault: {self.vault_path}")
                self.vault_indexer = VaultIndexer(self.vault_path, Path(self.db_dir), self.hippo.client)
            
            # 3. Hydrate state
            logger.info("[COGNITIVE] Hydrating working memory...")
            self._hydrate()
            
            # 4. Signal readiness (Enable Relay Plane)
            self.ready_event.set()
            logger.info("[COGNITIVE] Intelligence layer fully stabilized.")

            # 5. Trigger continuous scan loop if needed
            if self.vault_indexer and self.enable_auto_scan:
                asyncio.create_task(self._vault_scan_loop())
                
        except Exception as e:
            logger.error(f"[COGNITIVE] Startup rhythm interrupted: {e}")

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
                            content = payload.get("messages", [{}])[-1].get("content", "")
                            if content:
                                wm.items.append(WorkingMemoryItem(trace_id=row["trace_id"], content=content, timestamp=row["timestamp"]))
                        except: pass
        except Exception as e:
            logger.exception(f"Hydration failed: {e}")

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None,
                     offload_threshold: int = None, context_id: str = "default",
                     sync_distill: bool = False) -> str:
        """
        Ingest a user stimulus and optionally an assistant reaction.
        P18: Isolated by context_id.
        P34: Organized by semantic rooms.
        """
        # Phase 36: Ensure stabilization before any write operation
        await self.wait_until_ready()

        async with self._get_session_lock(context_id):
            wm = self._get_wm(context_id)
            room_id = self._get_current_room(context_id)
            
            # 1. Archive to Hippocampus (L2)
            trace_id = str(uuid.uuid4())
            search_text = payload.get("messages", [{}])[-1].get("content", "")
            
            self.hippo.save_trace(
                trace_id=trace_id,
                payload={"stimulus": payload, "reaction": reaction},
                search_text=search_text,
                context_id=context_id,
                room_id=room_id
            )
            
            # 2. Add to Working Memory (L1)
            wm.add_item(trace_id, search_text)
            
            # 3. Persistence (P22)
            self.hippo.save_wm_state(context_id, wm.items)
            
            # 4. Signal Analysis
            signals = self.decomposer.decompose(search_text)
            for s in signals:
                wm.boost_by_signal(s)
            
            # 5. Incremental Counter
            self._trace_counters[context_id] = self._trace_counters.get(context_id, 0) + 1
            
        # --- TRIGGER COGNITIVE TASKS (Outside session lock) ---
        
        # A. Room Detection (P34)
        if self.enable_room_detection and not sync_distill:
            asyncio.create_task(self._perform_room_detection(context_id, search_text))
            
        # B. Distillation (L2 -> L3)
        if self.enable_auto_distill:
            if self._trace_counters.get(context_id, 0) >= (offload_threshold or self.distill_threshold) or sync_distill:
                if sync_distill:
                    await self._auto_distill_worker(context_id)
                else:
                    asyncio.create_task(self._auto_distill_worker(context_id))
                self._trace_counters[context_id] = 0
                
        return trace_id

    async def _perform_room_detection(self, session_id: str, current_intent: str):
        try:
            async with self._get_session_lock(session_id):
                wm = self._get_wm(session_id)
                history = wm.get_active_contents()
                known = self._get_known_rooms(session_id)
            
            new_room = await self.room_detector.detect_room(history, current_intent, known)
            
            # Update room status (Quick lock)
            async with self._get_session_lock(session_id):
                if new_room:
                    self._current_rooms[session_id] = new_room
                    if session_id not in self._known_rooms: self._known_rooms[session_id] = {"general"}
                    self._known_rooms[session_id].add(new_room)
        except Exception as e: logger.error(f"[ROOM_DET_FAIL] {e}")

    async def _auto_distill_worker(self, session_id: str):
        """Background worker to refine L2 fragments into L3 facts."""
        try:
            async with self._get_session_lock(session_id):
                wm = self._get_wm(session_id)
                # Use Hippo to fetch raw historical content for LLM
                recent = self.hippo.get_recent_traces(limit=20, context_id=session_id)
                raw_history = []
                for r in reversed(recent):
                    content = self.hippo.get_content(r["trace_id"])
                    if content: raw_history.append(content)
            
            if not raw_history: return
            
            logger.info(f"[DISTILL] Starting distillation for session: {session_id}")
            new_summary = await self.neo.distill(raw_history, session_id)
            
            if new_summary:
                async with self._get_session_lock(session_id):
                    # P23: Prune Working Memory after successful distillation
                    wm.prune(keep_count=5)
                    self.hippo.save_wm_state(session_id, wm.items)
                logger.info(f"[DISTILL] Completed. L3 Summary updated for {session_id}")
        except Exception as e:
            logger.error(f"[DISTILL_ERROR] {e}")

    async def get_combined_context(self, context_id: str, query: str, max_chars: int = 2000) -> str:
        """
        Assemble the optimal context using Stack Math budget allocation.
        Priority: L3 Facts > Vault > L1 Working Memory > L2 Hippocampus.
        """
        # Ensure readiness
        if not self.ready_event.is_set():
            return ""

        async with self._get_session_lock(context_id):
            wm = self._get_wm(context_id)
            current_room = self._get_current_room(context_id)
            
            # Layer retrieval
            l3_summary = self.neo.get_summary(context_id) or ""
            vault_results = []
            if self.vault_indexer:
                vault_results = self.vault_indexer.search(query, limit=3)
            
            working_contents = wm.get_active_contents()
            
            # L2 Retrieval (Favor current room)
            # hippo.search returns List[str] (IDs), limit is handled by slicing
            l2_ids = self.hippo.search(query, context_id=context_id, room_id=current_room)
            l2_contents = [self.hippo.get_content(tid) for tid in l2_ids[:5]]
            l2_contents = [c for c in l2_contents if c]

            # --- STACK MATH ASSEMBLY ---
            # Budget calculation (Precision Budgeting P31)
            # Allocation Order: L3 > Vault > L1 > L2
            
            output_parts = []
            current_len = 0
            
            def try_add_section(header: str, content_list: List[str]):
                nonlocal current_len
                if not content_list: return
                
                section_header = f"\n=== {header} ===\n"
                section_content = "\n".join([f"- {c}" for c in content_list])
                
                total_section = section_header + section_content
                if current_len + len(total_section) <= (max_chars - 50): # 50 for wrapper
                    output_parts.append(total_section)
                    current_len += len(total_section)

            # 1. Neocortex (L3)
            if l3_summary:
                try_add_section("DISTILLED KNOWLEDGE (L3)", [l3_summary])
            
            # 2. Vault (External)
            if vault_results:
                try_add_section("EXTERNAL KNOWLEDGE (VAULT)", [f"# {r['title']}\n{r['content']}" for r in vault_results])
                
            # 3. Working Memory (L1)
            try_add_section("ACTIVE CONVERSATION (WORKING MEMORY)", working_contents)
            
            # 4. Hippocampus (L2)
            try_add_section("RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS)", l2_contents)

            if not output_parts: return ""
            
            wrapped = "[CLAWBRAIN MEMORY]" + "".join(output_parts) + "\n[END CLAWBRAIN MEMORY]"
            return wrapped

    async def _vault_scan_loop(self):
        """Independent rhythmic driver for Knowledge Bridge."""
        if not self.vault_indexer: return
        while self.enable_auto_scan:
            try:
                stats = await self.vault_indexer.scan()
                if stats["indexed"] > 0:
                    logger.info(f"[COGNITIVE] Vault Pulse: Indexed {stats['indexed']} files.")
            except Exception as e:
                logger.error(f"[VAULT_SCAN_ERROR] {e}")
            await asyncio.sleep(300) # Every 5 minutes
