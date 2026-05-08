# Generated from design/memory_router.md v1.15 / GEMINI.md Rule 12
import uuid
import json
import os
import asyncio
import logging
import time
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

from src.memory.storage import Hippocampus, clear_chroma_clients
from src.memory.working import WorkingMemory, WorkingMemoryItem
from src.memory.neocortex import Neocortex
from src.memory.room_detector import RoomDetector
from src.memory.vault_indexer import VaultIndexer
from src.memory.signals import SignalDecomposer
from src.utils.config import get_env
from src.utils.llm_client import LLMClient

load_dotenv()

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
    ClawBrain Memory Central Router v2 (Breathing Brain).
    Unified environment-aware and decoupled memory orchestration.
    """
    def __init__(self, db_dir: str, distill_url: str = None, distill_model: str = None, distill_provider: str = None, 
                 enable_room_detection: bool = True, distill_threshold: int = 50, enable_auto_scan: bool = True):
        self.db_dir = Path(db_dir)
        self.ready_event = asyncio.Event()
        self.hippo = None
        self.neo = None
        self.room_detector = None
        self.vault_indexer = None
        self.decomposer = None
        
        # Environmental Priority
        self.distill_url = distill_url or get_env("CLAWBRAIN_DISTILL_URL", "http://127.0.0.1:11434")
        self.distill_model = distill_model or get_env("CLAWBRAIN_DISTILL_MODEL", "gemma4:e4b")
        self.distill_provider = distill_provider or get_env("CLAWBRAIN_DISTILL_PROVIDER", "ollama")
        
        self.distill_threshold = distill_threshold
        self.enable_room_detection = enable_room_detection
        self.enable_auto_distill = True
        self.enable_auto_scan = enable_auto_scan
        
        self._wm_sessions: Dict[str, WorkingMemory] = {}
        self._current_rooms: Dict[str, str] = {}
        self._trace_counters: Dict[str, int] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._last_injections: Dict[str, Any] = {}
        self._cognitive_events: List[Dict] = []
        self._dirty_sessions: set = set()
        self._heartbeat_seconds = 30
        self._running = True
        self._integration_mode = "Native"
        
        self.cb_room = CircuitBreaker()
        self.cb_distill = CircuitBreaker()
        self.cb_heartbeat = CircuitBreaker()
        self.vault_path = get_env("CLAWBRAIN_VAULT_PATH")
        
        asyncio.create_task(self._async_init())

    async def _async_init(self):
        try:
            logger.info(f"[COGNITIVE] Initializing Memory Engine at {self.db_dir}...")
            self.hippo = Hippocampus(str(self.db_dir))
            
            # v1.16: Decoupled Initialization. Let components self-configure from environment
            # to ensure load_dotenv() values are correctly captured.
            self.neo = Neocortex(db_dir=str(self.db_dir))
            self.room_detector = RoomDetector(
                url=get_env("CLAWBRAIN_DISTILL_URL", "http://127.0.0.1:11434"),
                model=get_env("CLAWBRAIN_DISTILL_MODEL", "gemma4:e4b")
            )
            self.decomposer = SignalDecomposer()
            
            if self.vault_path:
                self.vault_indexer = VaultIndexer(self.vault_path, self.db_dir, client=self.hippo.client)
                if self.enable_auto_scan:
                    asyncio.create_task(self._vault_scan_loop())
            
            asyncio.create_task(self._heartbeat_loop())
            logger.info("[COGNITIVE] Intelligence stabilized.")
        except Exception as e:
            logger.exception(f"Initialization crash: {e}")
        finally:
            self.ready_event.set()

    async def wait_until_ready(self, timeout: float = 30.0):
        await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)

    def _log_event(self, layer: str, action: str, msg: str, data: dict = None):
        event = {"ts": time.time(), "layer": layer, "action": action, "msg": msg, "data": data or {}}
        self._cognitive_events.append(event)
        if len(self._cognitive_events) > 1000: self._cognitive_events.pop(0)

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
                    wm._cleanup()
                else:
                    recent = self.hippo.get_recent_traces(limit=15, session_id=session_id)
                    for row in reversed(recent):
                        p = self.hippo.get_full_payload(row["trace_id"])
                        if p:
                            stimulus = p.get("stimulus", p)
                            msgs = stimulus.get("messages", [])
                            for m in msgs:
                                if m.get("content"): wm.add_item(WorkingMemoryItem(trace_id=row["trace_id"], content=m["content"]))
            except Exception as e: logger.error(f"Hydration fail: {e}")
        return self._wm_sessions[session_id]

    def _get_current_room(self, session_id: str) -> str:
        return self._current_rooms.get(session_id, "general")

    async def ingest(self, stimulus: Dict[str, Any], session_id: str = "default", sync_distill: bool = False, offload_threshold: int = None, trace_id: str = None) -> str:
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            room_id = self._get_current_room(session_id)
            trace_id = trace_id or str(uuid.uuid4())
            search_text = " ".join([m.get("content", "") for m in stimulus.get("messages", []) if m.get("role") == "user"])
            
            wm = self._get_wm(session_id)
            for m in stimulus.get("messages", []):
                if m.get("content"): wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=m["content"]))
            
            self.hippo.save_trace(trace_id, stimulus, search_text=search_text, session_id=session_id, room_id=room_id, threshold=offload_threshold)
            self.hippo.save_wm_state(session_id, wm.items)
            self._dirty_sessions.add(session_id)
            
            if sync_distill: await self._auto_distill_worker(session_id)
            if self.enable_room_detection: asyncio.create_task(self._auto_room_worker(session_id, search_text))
            return trace_id

    async def _auto_room_worker(self, session_id: str, current_turn: str):
        if self.cb_room.is_open(): return
        try:
            wm = self._get_wm(session_id)
            history = [it.content for it in wm.items[-5:]]
            new_room = await self.room_detector.detect_room(history, current_turn, list(set(self._current_rooms.values())))
            if new_room and new_room != self._current_rooms.get(session_id):
                self._current_rooms[session_id] = new_room
            self.cb_room.record_success()
        except Exception: self.cb_room.record_failure()

    async def commit_turn(self, trace_id: str, payload: Dict[str, Any], reaction: Dict[str, Any], session_id: str, sync_distill: bool = False, offload_threshold: int = None):
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id)
            room_id = self._get_current_room(session_id)
            self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, session_id=session_id, room_id=room_id, threshold=offload_threshold)
            if reaction.get("content"): wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=reaction["content"]))
            self.hippo.save_wm_state(session_id, wm.items)
            self._dirty_sessions.add(session_id)

    async def pre_turn_pending(self, stimulus: Dict[str, Any], session_id: str = "default") -> str:
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            trace_id = str(uuid.uuid4())
            wm = self._get_wm(session_id)
            for m in stimulus.get("messages", []):
                if m.get("content"): wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=m["content"]))
            self.hippo.save_trace(trace_id, {"stimulus": stimulus, "reaction": None}, session_id=session_id)
            self.hippo.save_wm_state(session_id, wm.items)
            return trace_id

    async def orphan_turn(self, trace_id: str, payload: Dict[str, Any], error: str, session_id: str):
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            self.hippo.save_trace(trace_id, {"stimulus": payload, "error": error}, session_id=session_id)

    async def get_combined_context(self, session_id: str, query: str, max_chars: int = None) -> str:
        if max_chars is None: max_chars = int(get_env("CLAWBRAIN_MAX_CONTEXT_CHARS", 2000))
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id)
            l3_summary = self.neo.get_summary(session_id) or ""
            working_items = wm.get_active_items()
            
            stop_words = {"what", "how", "when", "where", "which", "who", "whom", "this", "that", "these", "those", "does", "done", "list", "tell", "show", "concisely", "reply", "only", "about"}
            query_words = re.findall(r'\b\w{3,}\b', query.lower())
            core_subjects = [w for w in query_words if w not in stop_words] 
            hard_anchors = self.decomposer.extract_entities(query) if self.decomposer else []
            
            def _is_satisfied(content: str, dist: float) -> tuple[bool, float]:
                low, upp = content.lower(), content.upper()
                hits = sum(1 for a in hard_anchors if a.upper() in upp)
                matches = sum(1 for s in core_subjects if s in low)
                cov = matches / len(core_subjects) if core_subjects else 1.0
                sim = max(0.0, 1.0 - dist)
                ok = hits > 0 or cov >= 0.2 or sim > 0.65 or (len(core_subjects) <= 1 and sim > 0.15)
                score = (hits * 150.0) + (cov * 100.0 * (1.0 + sim)) + (sim * 20.0)
                return ok, score

            sem_res = self.hippo.search(query, session_id, self._get_current_room(session_id), limit=25, include_distances=True)
            lex_ids = self.hippo.search_lexical(list(hard_anchors) + list(core_subjects)[:5], session_id, limit=25)
            
            cmap = {c["id"]: c["distance"] for c in sem_res}
            for lid in lex_ids:
                if lid not in cmap: cmap[lid] = 1.0 
            
            reranked, seen = [], set()
            for tid, dist in cmap.items():
                p = self.hippo.get_full_payload(tid)
                if not p: continue
                stim = p.get("stimulus", p)
                msgs = stim.get("messages", [])
                txt = " | ".join([f"{m.get('role','user')}: {m.get('content','')}" for m in msgs]) if msgs else (stim.get("content") or stim.get("text") or str(stim))
                if not txt or txt in seen: continue 
                ok, sc = _is_satisfied(txt, dist)
                if ok: reranked.append({"content": txt, "score": sc}); seen.add(txt)

            reranked.sort(key=lambda x: x["score"], reverse=True)
            l2_contents = [it["content"] for it in reranked]
            vault_results = []
            if self.vault_indexer:
                for r in self.vault_indexer.search(query, limit=5):
                    ok, sc = _is_satisfied(r["content"], r.get("distance", 1.0))
                    if ok: vault_results.append({"content": r["content"], "score": sc})
                vault_results.sort(key=lambda x: x["score"], reverse=True)

            potential_entities = list(hard_anchors)
            entity_facts = self.hippo.get_facts_for_entities(session_id, potential_entities)
            
            if not any([l3_summary, entity_facts, vault_results, l2_contents]): return ""
            
            sample = "\n".join([l3_summary] + l2_contents[:1] + [r["content"] for r in vault_results[:1]])
            if not await self.neo.verify_relevance(query, sample): return ""

            output_parts, cur_len = [], 0
            def try_add(header, contents, prefix="- "):
                nonlocal cur_len
                if not contents: return
                ht = f"\n\n=== {header} ===\n"
                if cur_len + len(ht) + 20 > max_chars: return
                lines = []
                for it in contents:
                    val = it["content"] if isinstance(it, dict) else it
                    line = f"{prefix}{val}"
                    if cur_len + len(ht) + len("\n".join(lines + [line])) <= max_chars: lines.append(line)
                    else: break
                if lines:
                    sec = ht + "\n".join(lines)
                    output_parts.append(sec); cur_len += len(sec)

            if l3_summary: try_add("SYSTEM MEMORY SUMMARY (NEOCORTEX)", [l3_summary])
            try_add("ACTIVE CONVERSATION (WORKING MEMORY)", [it.content for it in working_items])
            if entity_facts: try_add("ENTITY REGISTRY (VERIFIED FACTS)", [f"{f['entity']} > {f['key']}: {f['value']}" for f in entity_facts])
            if vault_results: try_add("EXTERNAL KNOWLEDGE (VAULT)", vault_results)
            try_add("RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS)", l2_contents, prefix="") 

            coupling = "\n\n[COGNITIVE COUPLING]: Cross-reference above facts. Prioritize NEOCORTEX."
            res = "[CLAWBRAIN MEMORY]" + "".join(output_parts)
            if len(res) + len(coupling) + 20 <= max_chars: res += coupling
            return res + "\n[END CLAWBRAIN MEMORY]"

    async def _heartbeat_loop(self):
        while self._running:
            if self.cb_heartbeat.is_open(): await asyncio.sleep(60); continue
            try:
                for sid in list(self._dirty_sessions): await self._auto_distill_worker(sid)
                self._dirty_sessions.clear()
                self.cb_heartbeat.record_success()
            except Exception: self.cb_heartbeat.record_failure()
            await asyncio.sleep(self._heartbeat_seconds)

    async def _auto_distill_worker(self, session_id: str):
        if self.cb_distill.is_open(): return
        try:
            recent = self.hippo.get_recent_traces(limit=50, session_id=session_id)
            if recent:
                payloads = [self.hippo.get_full_payload(t["trace_id"]) for t in recent]
                await self.neo.distill(session_id, [p for p in payloads if p])
            self.cb_distill.record_success()
        except Exception: self.cb_distill.record_failure()

    async def distill_session(self, session_id: str) -> str:
        await self._auto_distill_worker(session_id)
        return self.neo.get_summary(session_id)

    async def _vault_scan_loop(self):
        while self._running and self.vault_indexer:
            try: await self.vault_indexer.scan()
            except: pass
            await asyncio.sleep(300)

    async def aclose(self):
        self._running = False
        logger.info("[ROUTER] Closing memory engine connections...")
        clear_chroma_clients()
