# Generated from design/memory_router.md v1.5 / GEMINI.md Rule 12
import uuid
import json
import os
import asyncio
import logging
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import httpx
from dotenv import load_dotenv

load_dotenv() # Load from .env if present

from src.memory.storage import Hippocampus, clear_chroma_clients
from src.memory.working import WorkingMemory, WorkingMemoryItem
from src.memory.neocortex import Neocortex
from src.memory.room_detector import RoomDetector
from src.memory.vault_indexer import VaultIndexer
from src.memory.signals import SignalDecomposer
from src.memory.entities import EntityExtractor
from src.utils.llm_client import LLMClient

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
    Rule 12: Unified session_id terminology enforced.
    """
    def __init__(self, db_dir: str, distill_url: str = None, distill_model: str = None, distill_provider: str = "ollama", 
                 enable_room_detection: bool = True, distill_threshold: int = 50, enable_auto_scan: bool = True):
        self.db_dir = Path(db_dir)
        self.ready_event = asyncio.Event()
        self.hippo = None
        self.neo = None
        self.room_detector = None
        self.vault_indexer = None
        
        self.distill_url = os.getenv("CLAWBRAIN_DISTILL_URL", distill_url or "http://127.0.0.1:11434")
        self.distill_model = os.getenv("CLAWBRAIN_DISTILL_MODEL", distill_model or "gemma4:e4b")
        self.distill_provider = os.getenv("CLAWBRAIN_DISTILL_PROVIDER", distill_provider or "ollama")
        
        # Figure Justification: distill_threshold=50 (Design §2.1) - Optimal consolidation epoch.
        self.distill_threshold = distill_threshold
        self.enable_room_detection = enable_room_detection
        self.enable_auto_distill = True
        self.enable_auto_scan = enable_auto_scan
        
        self._wm_sessions: Dict[str, WorkingMemory] = {}
        self._current_rooms: Dict[str, str] = {}
        self._trace_counters: Dict[str, int] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._last_injections: Dict[str, Any] = {}
        
        # P61: Heartbeat Configuration (Design §2.5)
        self._dirty_sessions: Set[str] = set()
        self._pending_trace_extractions: List[str] = []
        # Figure Justification: heartbeat=30s - Balance between latency and batch efficiency.
        self._heartbeat_seconds = int(os.getenv("CLAWBRAIN_HEARTBEAT_SECONDS", 30))
        self._heartbeat_event = asyncio.Event()
        self._running = True
        
        self.cb_room = CircuitBreaker()
        self.cb_distill = CircuitBreaker()
        self.cb_heartbeat = CircuitBreaker()
        
        self.vault_path = os.getenv("CLAWBRAIN_VAULT_PATH")
        
        asyncio.create_task(self._async_init())

    async def _async_init(self):
        try:
            logger.info("[COGNITIVE] Establishing long-term memory engine...")
            self.hippo = Hippocampus(str(self.db_dir))
            self.neo = Neocortex(str(self.db_dir), self.distill_url, self.distill_model, self.distill_provider)
            self.room_detector = RoomDetector(url=self.distill_url, model=self.distill_model, provider=self.distill_provider)
            self.decomposer = SignalDecomposer()
            self.entity_extractor = EntityExtractor(self.hippo)
            
            if self.vault_path:
                self.vault_indexer = VaultIndexer(self.vault_path, self.db_dir, client=self.hippo.client)
                if self.enable_auto_scan:
                    asyncio.create_task(self._vault_scan_loop())
            
            # Start the Breathing Brain heartbeat loop (Phase 61)
            asyncio.create_task(self._cognitive_heartbeat_loop())
            logger.info("[COGNITIVE] Intelligence layer stabilized.")
        except Exception as e:
            logger.exception(f"Cognitive initialization failed: {e}")
        finally:
            self.ready_event.set()

    async def _cognitive_heartbeat_loop(self):
        """Phase 61: The Breathing Brain - Autonomous background orchestration."""
        logger.info(f"[HEARTBEAT] Loop started with rhythm: {self._heartbeat_seconds}s")
        while self._running:
            try:
                # Wait for the next rhythm pulse OR an external nudge
                try:
                    await asyncio.wait_for(self._heartbeat_event.wait(), timeout=self._heartbeat_seconds)
                    self._heartbeat_event.clear()
                except asyncio.TimeoutError:
                    pass

                if self.cb_heartbeat.is_open():
                    continue

                # 1. Process Trace Extractions (Issue #006 - LLM-based Mining)
                while self._pending_trace_extractions:
                    tid = self._pending_trace_extractions.pop(0)
                    payload = self.hippo.get_full_payload(tid)
                    if payload:
                        # Extract session_id from payload metadata if possible, fallback to default
                        sid = payload.get("session_id", "default")
                        await self.entity_extractor.extract_and_store(sid, tid, payload)

                # 2. Process Session Distillations (Knowledge Consolidation)
                dirty_copy = list(self._dirty_sessions)
                for session_id in dirty_copy:
                    async with self._get_session_lock(session_id):
                        await self._auto_distill_worker(session_id)
                        self._dirty_sessions.discard(session_id)

                self.cb_heartbeat.record_success()
            except Exception as e:
                logger.error(f"[HEARTBEAT] Cycle failed: {e}")
                self.cb_heartbeat.record_failure()

    async def wait_until_ready(self): await self.ready_event.wait()

    def nudge(self):
        """External trigger to force immediate cognitive activity (used in tests)."""
        self._heartbeat_event.set()

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
                            stimulus = p.get("stimulus") if "stimulus" in p else p
                            msgs = stimulus.get("messages", [])
                            if not msgs and "reaction" in p:
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
            
            search_parts = [m.get("content", "") for m in stimulus.get("messages", []) if m.get("role") == "user"]
            search_text = " ".join(search_parts) or stimulus.get("messages", [{}])[-1].get("content", "")
            
            wm = self._get_wm(session_id)
            for m in stimulus.get("messages", []):
                content = m.get("content", "")
                if content: 
                    wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=content))
                    entities = self.decomposer.extract_entities(content)
                    for entity in entities:
                        self.hippo.upsert_fact(session_id, entity, "mention", content, trace_id=trace_id)
            
            self.hippo.save_trace(trace_id, stimulus, search_text=search_text, session_id=session_id, room_id=room_id, threshold=offload_threshold)
            self.hippo.save_wm_state(session_id, wm.items)
            
            # P61: Decentralized tasks are now queued for the Heartbeat
            self._pending_trace_extractions.append(trace_id)
            self._trace_counters[session_id] = self._trace_counters.get(session_id, 0) + 1
            
            if self._trace_counters[session_id] >= self.distill_threshold or sync_distill:
                self._trace_counters[session_id] = 0
                if sync_distill: 
                    await self._auto_distill_worker(session_id)
                else:
                    self._dirty_sessions.add(session_id)
            
            if self.enable_room_detection:
                asyncio.create_task(self._auto_room_worker(session_id, search_text))
            
            return trace_id

    async def commit_turn(self, trace_id: str, payload: Dict[str, Any], reaction: Dict[str, Any], session_id: str, sync_distill: bool = False, offload_threshold: int = None):
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id)
            room_id = self._get_current_room(session_id)
            search_text = payload.get("messages", [{}])[-1].get("content", "")
            self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, search_text=search_text, session_id=session_id, room_id=room_id, threshold=offload_threshold)
            
            reaction_content = reaction.get("content", "")
            if reaction_content:
                wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=reaction_content))
                entities = self.decomposer.extract_entities(reaction_content)
                for entity in entities:
                    self.hippo.upsert_fact(session_id, entity, "verified", reaction_content, trace_id=trace_id)

            self.hippo.save_wm_state(session_id, wm.items)
            if trace_id not in self._pending_trace_extractions:
                self._pending_trace_extractions.append(trace_id)

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
                if content: 
                    wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=content))
                    entities = self.decomposer.extract_entities(content)
                    for entity in entities:
                        self.hippo.upsert_fact(session_id, entity, "mention", content, trace_id=trace_id)
            
            self.hippo.save_trace(trace_id, {"stimulus": stimulus, "reaction": None}, session_id=session_id)
            self.hippo.save_wm_state(session_id, wm.items)
            self._pending_trace_extractions.append(trace_id)
            return trace_id

    async def get_combined_context(self, session_id: str, query: str, max_chars: int = None) -> str:
        # Figure Justification: max_chars=2000 (Design §2.4) - Standard safe bound for augmentation.
        if max_chars is None: max_chars = int(os.getenv("CLAWBRAIN_MAX_CONTEXT_CHARS", 2000))
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id)
            l3_summary = self.neo.get_summary(session_id) or ""
            working_items = wm.get_active_items()
            working_contents = [it.content for it in working_items]
            
            stop_words = {"what", "how", "when", "where", "which", "who", "whom", "this", "that", "these", "those", "does", "done", "list", "tell", "show", "concisely", "reply", "only", "about"}
            query_words = re.findall(r'\b\w{3,}\b', query.lower())
            core_subjects = [w for w in query_words if w not in stop_words] 
            
            hard_anchors = self.decomposer.extract_entities(query)
            
            def _is_constraint_satisfied(content: str, distance: float) -> tuple[bool, float]:
                """Universal gate: Does this snippet SPECIFICALLY focus on the query subject?"""
                content_lower, content_upper = content.lower(), content.upper()
                
                # Figure Justification: Anchors*150 (Design §2.2.1) - Hard facts are primary signal.
                anchor_hits = sum(1 for a in hard_anchors if a.upper() in content_upper)
                # Figure Justification: Coverage*100 (Design §2.2.1) - Lexical overlap is secondary.
                matched_subjects = sum(1 for s in core_subjects if s in content_lower)
                subject_coverage = matched_subjects / len(core_subjects) if core_subjects else 1.0
                
                # Figure Justification: Similarity*20 (Design §2.2.1) - Fuzzy signal for tie-breaking.
                similarity = max(0.0, 1.0 - distance)
                
                # Figure Justification: coverage>=0.2 / semantic>0.65 (Design §2.2.2) - Wide Net Admission.
                is_ok = anchor_hits > 0 or subject_coverage >= 0.2 or similarity > 0.65 or (len(core_subjects) <= 1 and similarity > 0.15)
                score = (anchor_hits * 150.0) + (subject_coverage * 100.0 * (1.0 + similarity)) + (similarity * 20.0)
                return is_ok, score

            lex_tokens = list(hard_anchors) + list(core_subjects)[:5]
            sem_results = self.hippo.search(query, session_id, self._get_current_room(session_id), limit=25, include_distances=True)
            lex_ids = self.hippo.search_lexical(lex_tokens, session_id, limit=25)
            
            candidate_map = {c["id"]: c["distance"] for c in sem_results}
            for lid in lex_ids:
                if lid not in candidate_map: candidate_map[lid] = 1.0 
            
            reranked_items, seen_contents = [], set()
            for tid, distance in candidate_map.items():
                p = self.hippo.get_full_payload(tid)
                if not p: continue
                stimulus = p.get("stimulus", {}) if "stimulus" in p else p
                msgs = p.get("messages", []) or stimulus.get("messages", [])
                content_str = " | ".join([f"{m.get('role','user')}: {m.get('content','')}" for m in msgs]) if msgs else (stimulus.get("content") or stimulus.get("text") or str(stimulus))
                
                if not content_str or content_str in seen_contents: continue 
                is_ok, score = _is_constraint_satisfied(content_str, distance)
                if is_ok:
                    reranked_items.append({"content": content_str, "score": score})
                    seen_contents.add(content_str)

            reranked_items.sort(key=lambda x: x["score"], reverse=True)
            l2_contents = [it["content"] for it in reranked_items]

            vault_results = []
            if self.vault_indexer:
                raw_vault = self.vault_indexer.search(query, limit=5)
                for r in raw_vault:
                    is_ok, score = _is_constraint_satisfied(r["content"], r.get("distance", 1.0))
                    if is_ok: vault_results.append({"title": r["title"], "content": r["content"], "score": score})
                vault_results.sort(key=lambda x: x["score"], reverse=True)

            potential_entities = list(hard_anchors)
            entity_facts = self.hippo.get_facts_for_entities(session_id, potential_entities)
            
            has_long_term_gain = any([l3_summary, entity_facts, vault_results, l2_contents])
            if not has_long_term_gain: return ""
            
            sample_parts = []
            if l3_summary: sample_parts.append(l3_summary)
            if l2_contents: sample_parts.append(l2_contents[0])
            if vault_results: sample_parts.append(vault_results[0]["content"])
            if entity_facts: sample_parts.append(f"{entity_facts[0]['entity']}: {entity_facts[0]['value']}")
            
            context_sample = "\n".join(sample_parts)
            is_truly_relevant = await self.neo.verify_relevance(query, context_sample)
            if not is_truly_relevant: return ""

            output_parts, current_len = [], 0
            def try_add(header, contents, prefix="- "):
                nonlocal current_len
                if not contents: return
                ht = f"\n\n=== {header} ===\n"
                # Figure Justification: safety=20 (Design §2.4) - Prevent hanging headers.
                safety = 20 
                sl, tr = [], False
                for it in contents:
                    line = f"{prefix}{it['content'] if isinstance(it, dict) else it}"
                    if current_len + len(ht) + len(line) + safety <= max_chars: sl.append(line)
                    else: tr = True; break
                if sl:
                    if tr: sl.append(f"{prefix}...")
                    fs = ht + "\n".join(sl)
                    if current_len + len(fs) + safety <= max_chars: output_parts.append(fs); current_len += len(fs)

            if l3_summary: try_add("SYSTEM MEMORY SUMMARY (NEOCORTEX)", [l3_summary])
            try_add("ACTIVE CONVERSATION (WORKING MEMORY)", working_contents)
            if vault_results: try_add("EXTERNAL KNOWLEDGE (VAULT)", vault_results)
            
            all_l2 = []
            if entity_facts: all_l2.extend([f"VERIFIED FACT: {f['entity']} > {f['key']}: {f['value']}" for f in entity_facts])
            if l2_contents: all_l2.extend(l2_contents)
            try_add("RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS)", all_l2, prefix="") 

            coupling = "\n\n[COGNITIVE COUPLING]: Cross-reference above facts. Prioritize NEOCORTEX."
            final_output = "[CLAWBRAIN MEMORY]" + "".join(output_parts)
            if len(final_output) + len(coupling) + 20 <= max_chars: final_output += coupling
            return final_output + "\n[END CLAWBRAIN MEMORY]"

    async def _auto_distill_worker(self, session_id: str):
        if self.cb_distill.is_open(): return
        try:
            recent = self.hippo.get_recent_traces(limit=self.distill_threshold, session_id=session_id)
            if not recent: return
            payloads = [self.hippo.get_full_payload(t["trace_id"]) for t in recent if t]
            await self.neo.distill(session_id, [p for p in payloads if p])
            self.cb_distill.record_success()
        except Exception: self.cb_distill.record_failure()

    async def distill_session(self, session_id: str) -> str:
        await self._auto_distill_worker(session_id)
        return self.neo.get_summary(session_id)

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

    async def _vault_scan_loop(self):
        while self.vault_indexer:
            try:
                if self.vault_indexer.index_all()["indexed"] > 0: logger.info("Vault Indexed.")
            except: pass
            await asyncio.sleep(300)

    async def aclose(self):
        self._running = False
        logger.info("[ROUTER] Closing memory engine connections...")
        clear_chroma_clients()
        await LLMClient.aclose()
