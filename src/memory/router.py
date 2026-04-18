# Generated from design/memory_router.md v1.13
import uuid
import json
import os
import asyncio
import logging
import time
import re
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

class CircuitBreaker:
    """Phase 37: Cognitive Plane Circuit Breaker (Issue #16)"""
    def __init__(self, max_failures=3, backoff_seconds=60):
        self.max_failures = max_failures
        self.backoff_seconds = backoff_seconds
        self.failures = 0
        self.last_failure_time = 0

    def is_open(self) -> bool:
        if self.failures >= self.max_failures:
            if time.time() - self.last_failure_time > self.backoff_seconds:
                # Half-open: allow a trial request
                self.failures = self.max_failures - 1
                return False
            return True
        return False

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()

    def record_success(self):
        self.failures = 0

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
        
        # Phase 45: The X-Ray View Cache (v1.2)
        self._last_injections: Dict[str, Any] = {}
        
        # Phase 37: Circuit Breakers for Cognitive Plane (Issue #16)
        self.cb_room = CircuitBreaker(max_failures=3, backoff_seconds=60)
        self.cb_distill = CircuitBreaker(max_failures=3, backoff_seconds=120)
        
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

    def _get_wm(self, session_id: str) -> WorkingMemory:
        if session_id not in self._wm_sessions:
            wm = WorkingMemory()
            self._wm_sessions[session_id] = wm
            # Phase 33: Lazy on-demand hydration for this specific session
            try:
                snapshot = self.hippo.load_wm_state(session_id)
                if snapshot:
                    for row in snapshot:
                        item = WorkingMemoryItem(trace_id=row["trace_id"], content=row["content"], timestamp=row["timestamp"])
                        item.activation = row["activation"]
                        wm.items.append(item)
                else:
                    # Fallback to recent traces
                    recent = self.hippo.get_recent_traces(limit=15, session_id=session_id)
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
                logger.error(f"[ROUTER] Lazy hydration failed for {session_id}: {e}")
        return self._wm_sessions[session_id]

    def _hydrate(self):
        """Phase 33: Removed global hydration in favor of lazy session-specific loading."""
        pass

    async def pre_turn_pending(self, payload: Dict[str, Any], session_id: str = "default", offload_threshold: int = None) -> str:
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            room_id = self._get_current_room(session_id)
            trace_id = str(uuid.uuid4())
            search_text = payload.get("messages", [{}])[-1].get("content", "")
            
            self.hippo.save_trace(
                trace_id=trace_id,
                payload={"stimulus": payload, "reaction": None},
                search_text=search_text,
                session_id=session_id,
                room_id=room_id
            )
        return trace_id

    async def commit_turn(self, trace_id: str, payload: Dict[str, Any], reaction: Dict[str, Any], session_id: str, sync_distill: bool = False, offload_threshold: int = None):
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id)
            room_id = self._get_current_room(session_id)
            search_text = payload.get("messages", [{}])[-1].get("content", "")
            
            self.hippo.save_trace(
                trace_id=trace_id,
                payload={"stimulus": payload, "reaction": reaction},
                search_text=search_text,
                session_id=session_id,
                room_id=room_id
            )
            
            wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=search_text))
            self.hippo.save_wm_state(session_id, wm.items)
            
            core_intent = self.decomposer.extract_core_intent(payload)
            self._trace_counters[session_id] = self._trace_counters.get(session_id, 0) + 1
            
        if self.enable_room_detection and not sync_distill:
            asyncio.create_task(self._perform_room_detection(session_id, search_text))
            
        if self.enable_auto_distill:
            if self._trace_counters.get(session_id, 0) >= 10 or sync_distill: # Using hardcoded 10 for now
                if sync_distill:
                    await self._auto_distill_worker(session_id)
                else:
                    asyncio.create_task(self._auto_distill_worker(session_id))
                self._trace_counters[session_id] = 0

    async def orphan_turn(self, trace_id: str, payload: Dict[str, Any], error: str, session_id: str, offload_threshold: int = None):
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            room_id = self._get_current_room(session_id)
            search_text = payload.get("messages", [{}])[-1].get("content", "")
            
            self.hippo.save_trace(
                trace_id=trace_id,
                payload={"stimulus": payload, "reaction": {"error": error}},
                search_text=search_text,
                session_id=session_id,
                room_id=room_id
            )

    async def ingest(self, payload: Dict[str, Any], reaction: Dict[str, Any] = None,
                     offload_threshold: int = None, session_id: str = "default",
                     sync_distill: bool = False) -> str:
        """
        Ingest a user stimulus and optionally an assistant reaction.
        P18: Isolated by session_id.
        P34: Organized by semantic rooms.
        """
        trace_id = await self.pre_turn_pending(payload, session_id, offload_threshold)
        await self.commit_turn(trace_id, payload, reaction, session_id, sync_distill, offload_threshold)
        return trace_id


    async def _perform_room_detection(self, session_id: str, current_intent: str):
        if self.cb_room.is_open():
            logger.warning("[ROOM_DET] Circuit breaker is open. Skipping room detection.")
            return
        try:
            async with self._get_session_lock(session_id):
                wm = self._get_wm(session_id)
                history = wm.get_active_contents()
                known = self._get_known_rooms(session_id)
            
            new_room = await self.room_detector.detect_room(history, current_intent, known)
            if new_room and new_room.startswith("[Error]"):
                self.cb_room.record_failure()
                logger.error(f"[ROOM_DET_FAIL] {new_room}")
                return
            
            self.cb_room.record_success()
            # Update room status (Quick lock)
            async with self._get_session_lock(session_id):
                if new_room:
                    self._current_rooms[session_id] = new_room
                    if session_id not in self._known_rooms: self._known_rooms[session_id] = {"general"}
                    self._known_rooms[session_id].add(new_room)
        except Exception as e: 
            self.cb_room.record_failure()
            logger.error(f"[ROOM_DET_FAIL] {e}")

    async def _auto_distill_worker(self, session_id: str):
        """Background worker to refine L2 fragments into L3 facts."""
        if self.cb_distill.is_open():
            logger.warning("[DISTILL] Circuit breaker is open. Skipping distillation.")
            return
        try:
            async with self._get_session_lock(session_id):
                wm = self._get_wm(session_id)
                # Fetch full trace objects for LLM distillation
                recent = self.hippo.get_recent_traces(limit=20, context_id=session_id)
                raw_history = []
                for r in reversed(recent):
                    # Get the full dictionary payload (containing stimulus/reaction)
                    trace_obj = self.hippo.get_full_payload(r["trace_id"])
                    if trace_obj: raw_history.append(trace_obj)
            
            if not raw_history: return
            
            logger.info(f"[DISTILL] Starting distillation for session: {session_id}")
            new_summary = await self.neo.distill(session_id, raw_history)
            
            if new_summary and new_summary.startswith("[Error]"):
                self.cb_distill.record_failure()
                logger.error(f"[DISTILL_ERROR] {new_summary}")
                return
            
            if new_summary:
                self.cb_distill.record_success()
                async with self._get_session_lock(session_id):
                    # P23: Prune Working Memory after successful distillation
                    wm.prune(keep_count=5)
                    self.hippo.save_wm_state(session_id, wm.items)
                logger.info(f"[DISTILL] Completed. L3 Summary updated for {session_id}")
        except Exception as e:
            self.cb_distill.record_failure()
            logger.error(f"[DISTILL_ERROR] {e}")

    async def get_combined_context(self, session_id: str, query: str, max_chars: int = None) -> str:
        """
        Assemble the optimal context using Stack Math budget allocation.
        Priority: Entities > L3 Facts > Vault > L1 Working Memory > L2 Hippocampus.
        """
        if max_chars is None:
            max_chars = int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", 2000))

        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id)
            current_room = self._get_current_room(session_id)

            # Layer retrieval
            l3_summary = self.neo.get_summary(session_id) or ""
            vault_results = []
            if self.vault_indexer:
                vault_results = self.vault_indexer.search(query, limit=3)

            working_contents = wm.get_active_contents()

            # 4. Hippocampus (L2)
            # L2 Retrieval (Favor current room)
            # hippo.search(query, session_id, room_id) returns List[str] (IDs)
            l2_ids = self.hippo.search(query, session_id, current_room)

            # Phase 38: Sparse Data Semantic Search Fallback (Issue #19)
            if not l2_ids and query:
                logger.info(f"[ROUTER] Semantic search returned empty for '{query}'. Engaging sparse data fallback.")
                recent_traces = self.hippo.get_recent_traces(limit=50, session_id=session_id)
                query_lower = query.lower()
                for trace in recent_traces:
                    raw_content = trace.get("raw_content", "") or ""
                    if query_lower in raw_content.lower():
                        l2_ids.append(trace["trace_id"])
                        if len(l2_ids) >= 5:
                            break

            l2_contents = []
            for tid in l2_ids[:5]:
                full_payload = self.hippo.get_full_payload(tid)
                if full_payload:
                    stimulus = full_payload.get("stimulus", {})
                    # Phase 47: Robust content extraction from full payload
                    msgs = stimulus.get("messages", [])
                    turn_text = []
                    if msgs:
                        for m in msgs:
                            turn_text.append(f"{m.get('role', 'user')}: {m.get('content', '')}")

                    reaction = full_payload.get("reaction", {})
                    if reaction and "message" in reaction:
                        rm = reaction["message"]
                        turn_text.append(f"assistant: {rm.get('content', '')}")

                    if turn_text:
                        l2_contents.append(" | ".join(turn_text))
                else:
                    # Fallback to simple content
                    content = self.hippo.get_content(tid)
                    if content: l2_contents.append(content)
            # --- ENTITY LOOKUP (Phase 50) ---
            # Extract potential entities from current query (Basic noun extraction)
            potential_entities = re.findall(r'\b[A-Z][a-z0-9]+\b|\b[a-z0-9]+\.[a-z0-9]+\b', query or "")
            entity_facts = []
            if potential_entities:
                entity_facts = self.hippo.get_facts_for_entities(session_id, list(set(potential_entities)))
            # --- STACK MATH ASSEMBLY ---
            # Budget calculation (Precision Budgeting P31)
            # Allocation Order: Entities > L3 > Vault > L1 > L2
            
            output_parts = []
            current_len = 0
            
            def try_add_section(header: str, content_list: List[str], item_prefix: str = "- "):
                nonlocal current_len
                if not content_list: return
                
                # Double newline for clear separation
                section_header = f"\n\n=== {header} ===\n"
                section_content = "\n".join([f"{item_prefix}{c}" for c in content_list])
                
                total_section = section_header + section_content
                if current_len + len(total_section) <= (max_chars - 100): # 100 for wrapper/coupling
                    output_parts.append(total_section)
                    current_len += len(total_section)

            # 0. Entity Registry (New Priority #1)
            if entity_facts:
                fact_strings = [f"{f['entity']} > {f['key']}: {f['value']}" for f in entity_facts]
                try_add_section("ENTITY REGISTRY (VERIFIED FACTS)", fact_strings)

            # 1. Neocortex (L3)
            if l3_summary:
                try_add_section("SYSTEM MEMORY SUMMARY (NEOCORTEX)", [l3_summary], item_prefix="- ")
            
            # 2. Vault (External)
            if vault_results:
                try_add_section("EXTERNAL KNOWLEDGE (VAULT)", [f"# {r['title']}\n{r['content']}" for r in vault_results], item_prefix="- ")
                
            # 3. Working Memory (L1)
            try_add_section("ACTIVE CONVERSATION (WORKING MEMORY)", working_contents, item_prefix="- ")
            
            # 4. Hippocampus (L2) - Use a numbered list to allow model to refer to specific facts
            # Step 4: Enhanced Multi-Fact synthesis. If multiple snippets share keywords, group them.
            if l2_contents:
                try:
                    from collections import defaultdict
                    # Basic entity grouping (keyword-based)
                    groups = defaultdict(list)
                    for content in l2_contents:
                        # Extract potential entities (simple capitalization check or common tech words)
                        words = set(re.findall(r'\b[A-Z][a-z0-9]+\b|\b[a-z0-9]+\.[a-z0-9]+\b', content))
                        matched = False
                        for word in words:
                            if len(word) > 3:
                                groups[word].append(content)
                                matched = True
                                break
                        if not matched:
                            groups["general"].append(content)
                    
                    grouped_list = []
                    for topic, items in groups.items():
                        if topic == "general": continue
                        grouped_list.append(f"TOPIC [{topic}]:\n  " + "\n  ".join([f"- {i}" for i in items]))
                    if groups["general"]:
                        grouped_list.append("OTHER CONTEXT:\n  " + "\n  ".join([f"- {i}" for i in groups["general"]]))
                    
                    try_add_section("RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS)", grouped_list, item_prefix="")
                except Exception as e:
                    # Fallback to simple list if grouping fails
                    logger.error(f"[ASSEMBLE] Grouping failed: {e}")
                    try_add_section("RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS)", l2_contents, item_prefix="FACT_")

            if not output_parts: return ""
            
            # Phase 39: Cognitive Coupling Instruction (Refined)
            coupling = ("\n\n[COGNITIVE COUPLING]: You MUST cross-reference facts from the sections above "
                        "to provide a unified answer. Facts grouped by TOPIC are related and should be synthesized. "
                        "If facts conflict, prioritize NEOCORTEX over HIPPOCAMPUS.")
            
            wrapped = "[CLAWBRAIN MEMORY]" + "".join(output_parts) + coupling + "\n[END CLAWBRAIN MEMORY]"
            return wrapped

    async def _auto_distill_worker(self, session_id: str):
        """Background worker to perform recursive summarization (Phase 40)."""
        if self.cb_distill.is_open:
            return
        
        try:
            # Fetch last 50 traces for this specific session
            recent = self.hippo.get_recent_traces(limit=50, session_id=session_id)
            if not recent:
                return
            
            # Extract full payloads
            full_traces = []
            for t in recent:
                p = self.hippo.get_full_payload(t["trace_id"])
                if p: full_traces.append(p)
            
            if not full_traces:
                return

            logger.info(f"[DISTILL] Triggering distillation for session: {session_id}")
            summary = await self.neo.distill(session_id, full_traces)
            
            if summary and not summary.startswith("[Error]"):
                self.cb_distill.record_success()
                logger.info(f"[DISTILL] Completed. L3 Summary updated for {session_id}")
            else:
                logger.warning(f"[DISTILL] Provider returned error: {summary}")
                self.cb_distill.record_failure()
                
        except Exception as e:
            logger.exception(f"Auto-distill failed for {session_id}: {e}")
            self.cb_distill.record_failure()

    async def distill_session(self, session_id: str) -> str:
        """Manually trigger and return the latest summary."""
        await self._auto_distill_worker(session_id)
        return self.neo.get_summary(session_id)

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

    async def aclose(self):
        """Phase 45: Graceful resource release (v1.2)."""
        logger.info("[ROUTER] Closing memory engine connections...")
        if hasattr(self, "internal_client"):
            await self.internal_client.aclose()
        # ChromaDB persistent client handles its own cleanup, 
        # but we could add more explicit clearing here if needed.
        from src.memory.storage import clear_chroma_clients
        clear_chroma_clients()
