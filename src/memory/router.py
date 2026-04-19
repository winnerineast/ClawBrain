# Generated from design/memory_router.md v1.13 / GEMINI.md Rule 12
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
from src.memory.neocortex import Neocortex
from src.memory.room_detector import RoomDetector
from src.memory.vault_indexer import VaultIndexer
from src.memory.signals import SignalDecomposer

logger = logging.getLogger("GATEWAY.MEMORY.ROUTER")

class CircuitBreaker:
    def __init__(self, max_failures: int = 3, backoff_seconds: int = 60):
        self.max_failures = max_failures
        self.backoff_seconds = backoff_seconds
        self.failures = 0
        self.last_failure_time = 0
    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
    def record_success(self): self.failures = 0
    def is_open(self) -> bool:
        if self.failures >= self.max_failures:
            if time.time() - self.last_failure_time < self.backoff_seconds: return True
            self.failures = 0
        return False

class MemoryRouter:
    """
    ClawBrain Memory Central Router.
    Rule 12: Unified session_id terminology enforced.
    """
    def __init__(self, db_dir: str, distill_url: str = None, distill_model: str = None, distill_provider: str = "ollama", 
                 enable_room_detection: bool = True, distill_threshold: int = 10, enable_auto_scan: bool = True):
        self.db_dir = Path(db_dir)
        self.ready_event = asyncio.Event()
        self.hippo = None
        self.neo = None
        self.room_detector = None
        self.vault_indexer = None
        
        self.distill_url = os.getenv("CLAWBRAIN_DISTILL_URL", distill_url or "http://127.0.0.1:11434")
        self.distill_model = os.getenv("CLAWBRAIN_DISTILL_MODEL", distill_model or "gemma4:e4b")
        self.distill_provider = distill_provider
        self.distill_threshold = distill_threshold
        self.enable_room_detection = enable_room_detection
        self.enable_auto_distill = True
        self.enable_auto_scan = enable_auto_scan
        
        self._wm_sessions: Dict[str, WorkingMemory] = {}
        self._current_rooms: Dict[str, str] = {}
        self._trace_counters: Dict[str, int] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._last_injections: Dict[str, Any] = {}
        
        self.cb_room = CircuitBreaker()
        self.cb_distill = CircuitBreaker()
        self.vault_path = os.getenv("CLAWBRAIN_VAULT_PATH")
        
        asyncio.create_task(self._async_init())

    async def _async_init(self):
        try:
            logger.info("[COGNITIVE] Establishing long-term memory engine...")
            self.hippo = Hippocampus(str(self.db_dir))
            self.neo = Neocortex(str(self.db_dir), self.distill_url, self.distill_model, self.distill_provider)
            self.room_detector = RoomDetector(url=self.distill_url, model=self.distill_model)
            self.decomposer = SignalDecomposer()
            
            if self.vault_path:
                self.vault_indexer = VaultIndexer(self.vault_path, self.db_dir, client=self.hippo.client)
                if self.enable_auto_scan:
                    asyncio.create_task(self._vault_scan_loop())
                
            logger.info("[COGNITIVE] Intelligence layer stabilized.")
        except Exception as e:
            logger.exception(f"Cognitive initialization failed: {e}")
        finally:
            self.ready_event.set()

    async def wait_until_ready(self): await self.ready_event.wait()

    def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._session_locks: self._session_locks[session_id] = asyncio.Lock()
        return self._session_locks[session_id]

    def _get_wm(self, session_id: str) -> WorkingMemory:
        if session_id not in self._wm_sessions:
            wm = WorkingMemory()
            self._wm_sessions[session_id] = wm
            try:
                snapshot = self.hippo.load_wm_state(session_id)
                if snapshot:
                    for row in snapshot:
                        wm.items.append(WorkingMemoryItem(trace_id=row["trace_id"], content=row["content"], timestamp=row["timestamp"], activation=row["activation"]))
                    # Phase 22 fix: Ensure restored items are sorted by activation to match before-restart state
                    wm._cleanup()
                else:
                    recent = self.hippo.get_recent_traces(limit=15, session_id=session_id)
                    for row in reversed(recent):
                        p = self.hippo.get_full_payload(row["trace_id"])
                        if p:
                            # Robust extraction: handle both direct stimulus and stimulus-wrapped payloads
                            stimulus = p.get("stimulus") if "stimulus" in p else p
                            msgs = stimulus.get("messages", [])

                            if not msgs and "reaction" in p: # Reaction check for solidification
                                msgs = [{"role": "assistant", "content": p["reaction"].get("content", "")}]

                            for m in msgs:
                                content = m.get("content", "")
                                if content: wm.add_item(WorkingMemoryItem(trace_id=row["trace_id"], content=content, timestamp=row["timestamp"]))

            except Exception as e: logger.error(f"[ROUTER] Hydration failed for {session_id}: {e}")
        return self._wm_sessions[session_id]

    def _get_current_room(self, session_id: str) -> str:
        return self._current_rooms.get(session_id, "general")

    async def ingest(self, stimulus: Dict[str, Any], session_id: str = "default", sync_distill: bool = False, offload_threshold: int = None, trace_id: str = None) -> str:
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            room_id = self._get_current_room(session_id)
            trace_id = trace_id or str(uuid.uuid4())
            
            # P47: Composite search text from all user messages in stimulus
            search_parts = [m.get("content", "") for m in stimulus.get("messages", []) if m.get("role") == "user"]
            search_text = " ".join(search_parts) or stimulus.get("messages", [{}])[-1].get("content", "")
            
            wm = self._get_wm(session_id)
            # P47: Ensure all messages in stimulus are in WM (Assistant might be pre-filled)
            for m in stimulus.get("messages", []):
                content = m.get("content", "")
                if content: wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=content))
            
            self.hippo.save_trace(trace_id, stimulus, search_text=search_text, session_id=session_id, room_id=room_id, threshold=offload_threshold)
            self.hippo.save_wm_state(session_id, wm.items)
            
            self._trace_counters[session_id] = self._trace_counters.get(session_id, 0) + 1
            if self._trace_counters[session_id] >= self.distill_threshold or sync_distill:
                self._trace_counters[session_id] = 0
                if sync_distill: await self._auto_distill_worker(session_id)
                else: asyncio.create_task(self._auto_distill_worker(session_id))
            
            # Phase 34: Background Room Detection
            if self.enable_room_detection:
                asyncio.create_task(self._auto_room_worker(session_id, search_text))
            
            return trace_id

    async def _auto_room_worker(self, session_id: str, current_turn: str):
        if self.cb_room.is_open(): return
        try:
            wm = self._get_wm(session_id)
            history = [it.content for it in wm.items[-5:]]
            existing = list(set(self._current_rooms.values()))
            
            new_room = await self.room_detector.detect_room(history, current_turn, existing)
            if new_room and new_room != self._current_rooms.get(session_id):
                logger.info(f"[ROUTER] Topic shift detected in {session_id}: -> {new_room}")
                self._current_rooms[session_id] = new_room
            self.cb_room.record_success()
        except Exception as e:
            logger.warning(f"[ROUTER] Room detection background fail: {e}")
            self.cb_room.record_failure()

    async def commit_turn(self, trace_id: str, payload: Dict[str, Any], reaction: Dict[str, Any], session_id: str, sync_distill: bool = False, offload_threshold: int = None):
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id)
            room_id = self._get_current_room(session_id)
            search_text = payload.get("messages", [{}])[-1].get("content", "")
            self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, search_text=search_text, session_id=session_id, room_id=room_id, threshold=offload_threshold)
            
            # P47: Add reaction (Assistant message) to Working Memory
            reaction_content = reaction.get("content", "")
            if reaction_content:
                wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=reaction_content))
            
            self.hippo.save_wm_state(session_id, wm.items)

    async def orphan_turn(self, trace_id: str, payload: Dict[str, Any], error: str, session_id: str):
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            self.hippo.save_trace(trace_id, {"stimulus": payload, "error": error}, session_id=session_id)

    async def pre_turn_pending(self, stimulus: Dict[str, Any], session_id: str = "default") -> str:
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            trace_id = str(uuid.uuid4())
            wm = self._get_wm(session_id)
            for m in stimulus.get("messages", []):
                content = m.get("content", "")
                if content: wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=content))
            
            self.hippo.save_trace(trace_id, {"stimulus": stimulus, "reaction": None}, session_id=session_id)
            self.hippo.save_wm_state(session_id, wm.items)
            return trace_id

    async def get_combined_context(self, session_id: str, query: str, max_chars: int = None) -> str:
        if max_chars is None: max_chars = int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", 2000))
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id)
            l3_summary = self.neo.get_summary(session_id) or ""
            working_items = wm.get_active_items()
            working_contents = [it.content for it in working_items]
            
            l2_ids = self.hippo.search(query, session_id, self._get_current_room(session_id))
            if not l2_ids and query:
                recent = self.hippo.get_recent_traces(limit=20, session_id=session_id)
                l2_ids = [t["trace_id"] for t in recent if query.lower() in str(t["raw_content"]).lower()][:5]

            l2_contents = []
            for tid in l2_ids:
                p = self.hippo.get_full_payload(tid)
                if p:
                    # P47: Robust extraction for historical snippets
                    msgs = p.get("messages", []) or p.get("stimulus", {}).get("messages", [])
                    if not msgs and "reaction" in p:
                        msgs = [{"role": "assistant", "content": p["reaction"].get("content", "")}]
                    elif not msgs and p.get("stimulus", {}).get("content"): # Robustness for manual test plants
                        msgs = [{"role": "user", "content": p["stimulus"]["content"]}]
                        
                    turn = [f"{m.get('role','user')}: {m.get('content','')}" for m in msgs]
                    if turn:
                        l2_contents.append(" | ".join(turn))

            vault_results = self.vault_indexer.search(query, limit=3) if self.vault_indexer else []
            potential_entities = re.findall(r'\b[A-Z][a-z0-9]+\b|\b[a-z0-9]+\.[a-z0-9]+\b', query or "")
            entity_facts = self.hippo.get_facts_for_entities(session_id, list(set(potential_entities)))
            
            output_parts = []
            current_len = 0
            
            # P31: Strict Header + Safety Margin checks (as per design/memory_router.md §2.6)
            def try_add(header, contents, prefix="- "):
                nonlocal current_len
                if not contents: return
                header_text = f"\n\n=== {header} ===\n"
                
                # Header safety: header_text + buffer (approx 20 chars)
                if current_len + len(header_text) + 20 > max_chars:
                    return

                section_lines = []
                # Greedily add contents within budget
                for it in contents:
                    line = f"{prefix}{it}"
                    # Check if adding this line + header + current total exceeds max_chars
                    potential_full = header_text + "\n".join(section_lines + [line])
                    if current_len + len(potential_full) <= max_chars:
                        section_lines.append(line)
                    else:
                        break
                
                if section_lines:
                    full_section = header_text + "\n".join(section_lines)
                    output_parts.append(full_section)
                    current_len += len(full_section)

            # Design v1.13 Priority: L3 -> L1 -> L2
            if entity_facts: try_add("ENTITY REGISTRY (VERIFIED FACTS)", [f"{f['entity']} > {f['key']}: {f['value']}" for f in entity_facts])
            if l3_summary: try_add("SYSTEM MEMORY SUMMARY (NEOCORTEX)", [l3_summary])
            if vault_results: try_add("EXTERNAL KNOWLEDGE (VAULT)", [f"# {r['title']}\n{r['content']}" for r in vault_results])
            
            # L1: Working Memory
            try_add("ACTIVE CONVERSATION (WORKING MEMORY)", working_contents)
            
            # L2: Hippocampus (Episodic)
            try_add("RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS)", l2_contents, prefix="") 

            if not output_parts: return ""
            coupling = "\n\n[COGNITIVE COUPLING]: Cross-reference above facts. Prioritize NEOCORTEX."
            # Ensure coupling fits
            final_output = "[CLAWBRAIN MEMORY]" + "".join(output_parts)
            if len(final_output) + len(coupling) + 20 <= max_chars:
                final_output += coupling
            return final_output + "\n[END CLAWBRAIN MEMORY]"

    async def _auto_distill_worker(self, session_id: str):
        if self.cb_distill.is_open(): return
        try:
            recent = self.hippo.get_recent_traces(limit=50, session_id=session_id)
            if not recent: return
            payloads = [self.hippo.get_full_payload(t["trace_id"]) for t in recent if t]
            await self.neo.distill(session_id, [p for p in payloads if p])
            self.cb_distill.record_success()
        except Exception: self.cb_distill.record_failure()

    async def distill_session(self, session_id: str) -> str:
        await self._auto_distill_worker(session_id)
        return self.neo.get_summary(session_id)

    async def _vault_scan_loop(self):
        while self.vault_indexer:
            try:
                if self.vault_indexer.index_all()["indexed"] > 0: logger.info("Vault Indexed.")
            except: pass
            await asyncio.sleep(300)

    async def aclose(self):
        logger.info("[ROUTER] Closing memory engine connections...")
        clear_chroma_clients()
