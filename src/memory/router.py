# Generated from design/memory_router.md v1.21 / GEMINI.md Rule 12
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
from src.memory.entities import EntityExtractor

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
                 enable_room_detection: bool = True, distill_threshold: int = 10, enable_auto_scan: bool = True,
                 cb_max_failures: int = None, cb_backoff: int = None, judge_timeout: float = 2.0,
                 heartbeat_interval: int = None, enable_cognitive_plane: bool = True):
        self.db_dir = Path(db_dir)
        self.ready_event = asyncio.Event()
        self.hippo = None
        self.neo = None
        self.room_detector = None
        self.vault_indexer = None
        self.entity_extractor = None
        self.enable_cognitive_plane = enable_cognitive_plane
        
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
        
        # v0.2: Breathing Brain state
        self._dirty_sessions = set() # Sessions needing distillation
        self._pending_trace_extractions = [] # List of (session_id, trace_id) for entity extraction
        self.heartbeat_interval = int(os.getenv("CLAWBRAIN_HEARTBEAT_SECONDS", heartbeat_interval or 30))
        self._nudge_event = asyncio.Event() # v0.2.1: Manual nudge for testing
        
        # P56: Configurable Circuit Breakers
        self.cb_max_failures = int(os.getenv("CLAWBRAIN_CB_MAX_FAILURES", cb_max_failures or 3))
        self.cb_backoff = int(os.getenv("CLAWBRAIN_CB_BACKOFF", cb_backoff or 60))
        
        self.cb_room = CircuitBreaker(max_failures=self.cb_max_failures, backoff_seconds=self.cb_backoff)
        self.cb_distill = CircuitBreaker(max_failures=self.cb_max_failures, backoff_seconds=self.cb_backoff)
        
        # P56: Cognitive Judge Timeout
        self.judge_timeout = float(os.getenv("CLAWBRAIN_JUDGE_TIMEOUT", judge_timeout))
        self.vault_path = os.getenv("CLAWBRAIN_VAULT_PATH")
        
        asyncio.create_task(self._async_init())

    async def _async_init(self):
        try:
            logger.info("[COGNITIVE] Establishing long-term memory engine...")
            self.hippo = Hippocampus(str(self.db_dir))
            self.neo = Neocortex(str(self.db_dir), self.distill_url, self.distill_model, self.distill_provider, hippo=self.hippo)
            self.room_detector = RoomDetector(url=self.distill_url, model=self.distill_model)
            self.entity_extractor = EntityExtractor(url=self.distill_url, model=self.distill_model, provider=self.distill_provider)
            self.decomposer = SignalDecomposer()
            
            if self.vault_path:
                self.vault_indexer = VaultIndexer(self.vault_path, self.db_dir, client=self.hippo.client)
                if self.enable_auto_scan and self.enable_cognitive_plane:
                    asyncio.create_task(self._vault_scan_loop())
            
            # v0.2: Start the background heartbeat
            if self.enable_cognitive_plane:
                asyncio.create_task(self._cognitive_heartbeat_loop())
                
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
            
            # v0.2: Queue for background brain (Heartbeat)
            self._trace_counters[session_id] = self._trace_counters.get(session_id, 0) + 1
            if self._trace_counters[session_id] >= self.distill_threshold or sync_distill:
                if sync_distill: 
                    await self._auto_distill_worker(session_id)
                    self._trace_counters[session_id] = 0
                else:
                    self._dirty_sessions.add(session_id)
            
            # Phase 34: Background Room Detection (Kept as separate task for focus)
            if self.enable_room_detection:
                asyncio.create_task(self._auto_room_worker(session_id, search_text))
            
            # v0.2: Queue entity extraction for Heartbeat
            if self.entity_extractor:
                self._pending_trace_extractions.append((session_id, trace_id))
            
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
            
            # v0.2: Queue entity extraction for Heartbeat
            if self.entity_extractor:
                self._pending_trace_extractions.append((session_id, trace_id))

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
            
            # Phase 55: Universal Cognitive Filter (v1.22 - Density Gating)
            # 1. Precise Intent Extraction
            stop_words = {"what", "how", "when", "where", "which", "who", "whom", "this", "that", "these", "those", "does", "done", "list", "tell", "show", "concisely", "reply", "only", "about"}
            query_words = re.findall(r'\b\w{3,}\b', query.lower())
            core_subjects = [w for w in query_words if w not in stop_words and len(w) >= 4]
            hard_anchors = set(re.findall(r'\b(?:[A-Z0-9_\-\.]{3,}|[A-Z][a-z]+[0-9]*)\b', query))
            
            def _is_constraint_satisfied(content: str, distance: float) -> tuple[bool, float]:
                """Universal gate: Does this snippet SPECIFICALLY focus on the query subject?"""
                content_lower = content.lower()
                content_upper = content.upper()
                
                # Check 1: Hard Anchor match (Identity)
                anchor_hits = sum(1 for a in hard_anchors if a.upper() in content_upper)
                
                # Check 2: Subject Density (Focus)
                matched_subjects = sum(1 for s in core_subjects if s in content_lower)
                subject_coverage = matched_subjects / len(core_subjects) if core_subjects else 1.0
                
                # Check 3: Semantic Proximity
                similarity = max(0.0, 1.0 - distance)
                
                # --- UNIVERSAL ADMISSION RULES (v1.22) ---
                is_ok = False
                # Rule A: Hard Anchor match is always accepted
                if anchor_hits > 0:
                    is_ok = True
                # Rule B: High-Density Subject match (>= 70% coverage)
                elif subject_coverage >= 0.7:
                    is_ok = True
                # Rule C: Moderate Density (>= 50%) with reasonable similarity
                elif subject_coverage >= 0.5 and similarity > 0.4:
                    is_ok = True
                # Rule D: Extreme Semantic parity (Fallback)
                elif similarity > 0.8:
                    is_ok = True
                
                score = (anchor_hits * 150.0) + (subject_coverage * 60.0) + (similarity * 15.0)
                return is_ok, score

            # --- Phase 56: Thought-Driven Retrieval (v0.2) ---
            # 1. Search for High-level Thoughts
            thoughts = self.hippo.search_thoughts(query, session_id, limit=5)
            
            # 2. Resolve Root Sources for found thoughts
            thought_evidence = []
            source_trace_ids = []
            for t in thoughts:
                source_trace_ids.extend(t["source_traces"])
            
            if source_trace_ids:
                # Deduplicate and limit source traces
                source_trace_ids = list(set(source_trace_ids))[:10]
                resolved = self.hippo.get_traces_by_ids(source_trace_ids)
                for r in resolved:
                    p = r["payload"]
                    msgs = p.get("messages", []) or p.get("stimulus", {}).get("messages", [])
                    content_str = " | ".join([f"{m.get('role','user')}: {m.get('content','')}" for m in msgs])
                    thought_evidence.append(content_str)

            # 3. Search for Entities
            potential_entities = re.findall(r'\b[A-Z][a-z0-9]+\b|\b[a-z0-9]+\.[a-z0-9]+\b', query or "")
            entity_facts = self.hippo.get_facts_for_entities(session_id, list(set(potential_entities)))

            # 4. Search Vault
            vault_results = []
            if self.vault_indexer:
                raw_vault = self.vault_indexer.search(query, limit=5)
                for r in raw_vault:
                    is_ok, score = _is_constraint_satisfied(r["content"], r.get("distance", 1.0))
                    if is_ok:
                        vault_results.append({"title": r["title"], "content": r["content"], "score": score})
                vault_results.sort(key=lambda x: x["score"], reverse=True)

            # 5. L2 Fallback (Only if no high-level gains found)
            l2_contents = []
            if not thoughts and not entity_facts and not vault_results:
                sem_results = self.hippo.search(query, session_id, self._get_current_room(session_id), limit=25, include_distances=True)
                lex_ids = self.hippo.search_lexical(list(hard_anchors) + core_subjects[:5], session_id, limit=25)
                
                candidate_map = {c["id"]: c["distance"] for c in sem_results}
                for lid in lex_ids:
                    if lid not in candidate_map: candidate_map[lid] = 1.0 
                
                reranked_items = []
                seen_contents = set()
                for tid, distance in candidate_map.items():
                    p = self.hippo.get_full_payload(tid)
                    if not p: continue
                    msgs = p.get("messages", []) or p.get("stimulus", {}).get("messages", [])
                    content_str = " | ".join([f"{m.get('role','user')}: {m.get('content','')}" for m in msgs])
                    if content_str in seen_contents: continue 
                    
                    is_ok, score = _is_constraint_satisfied(content_str, distance)
                    if is_ok:
                        reranked_items.append({"content": content_str, "score": score})
                        seen_contents.add(content_str)

                reranked_items.sort(key=lambda x: x["score"], reverse=True)
                l2_contents = [it["content"] for it in reranked_items]

            # Phase 55: Contextual Silence (v1.23)
            has_long_term_gain = any([thoughts, l3_summary, entity_facts, vault_results, l2_contents])
            if not has_long_term_gain:
                return ""
            
            # --- CONTEXT ASSEMBLY (Strict Read-Only) ---
            output_parts = []
            current_len = 0
            
            # P31: Strict Header + Safety Margin checks (as per design/memory_router.md §2.6)
            def try_add(header, contents, prefix="- "):
                nonlocal current_len
                if not contents: return
                header_text = f"\n\n=== {header} ===\n"
                
                if current_len + len(header_text) + 20 > max_chars:
                    return

                section_lines = []
                is_truncated = False
                for it in contents:
                    # Support for structured results (Vault uses dicts)
                    content_val = it["content"] if isinstance(it, dict) else it
                    line = f"{prefix}{content_val}"
                    potential_full = header_text + "\n".join(section_lines + [line])
                    if current_len + len(potential_full) <= max_chars:
                        section_lines.append(line)
                    else:
                        is_truncated = True
                        break
                
                if section_lines:
                    if is_truncated:
                        section_lines.append(f"{prefix}...")
                    full_section = header_text + "\n".join(section_lines)
                    output_parts.append(full_section)
                    current_len += len(full_section)

            # Design v1.14 Priority: L3 -> L1 -> Vault -> L2
            if thoughts:
                thought_lines = [f"{t['thought']} (Confidence: {t['confidence']})" for t in thoughts]
                try_add("VERIFIED THOUGHTS (NEOCORTEX)", thought_lines)
                if thought_evidence:
                    try_add("SUPPORTING EVIDENCE (ROOT SOURCES)", thought_evidence)
            elif l3_summary:
                try_add("SYSTEM MEMORY SUMMARY (NEOCORTEX)", [l3_summary])

            try_add("ACTIVE CONVERSATION (WORKING MEMORY)", working_contents)
            
            # Entities and Vault
            if entity_facts: try_add("ENTITY REGISTRY (VERIFIED FACTS)", [f"{f['entity']} > {f['key']}: {f['value']}" for f in entity_facts])
            if vault_results: try_add("EXTERNAL KNOWLEDGE (VAULT)", vault_results)
            
            # L2: Hippocampus (Episodic)
            if l2_contents:
                try_add("RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS)", l2_contents, prefix="") 

            coupling = "\n\n[COGNITIVE COUPLING]: Cross-reference above facts. Prioritize NEOCORTEX."
            final_output = "[CLAWBRAIN MEMORY]" + "".join(output_parts)
            if len(final_output) + len(coupling) + 20 <= max_chars:
                final_output += coupling
            return final_output + "\n[END CLAWBRAIN MEMORY]"

    async def _auto_distill_worker(self, session_id: str):
        if self.cb_distill.is_open(): 
            logger.debug(f"[DISTILL] Circuit breaker open for {session_id}")
            return
        try:
            recent = self.hippo.get_recent_traces(limit=50, session_id=session_id)
            if not recent: 
                logger.debug(f"[DISTILL] No recent traces for {session_id}")
                return
            
            # recent already contains [{"trace_id": "...", "payload": {...}, ...}]
            logger.debug(f"[DISTILL] Distilling {len(recent)} traces for {session_id}.")
            res = await self.neo.distill(session_id, recent)
            logger.debug(f"[DISTILL] Neocortex.distill result: {res}")
            self.cb_distill.record_success()
        except Exception as e: 
            logger.error(f"[DISTILL] Exception: {e}")
            self.cb_distill.record_failure()

    async def _auto_entity_worker(self, session_id: str, trace_id: str):
        """Background extraction of entities from a specific turn."""
        try:
            p = self.hippo.get_full_payload(trace_id)
            if not p: return
            
            # Reconstruct dialogue for extraction
            msgs = p.get("messages", []) or p.get("stimulus", {}).get("messages", [])
            reaction = p.get("reaction")
            if reaction:
                msgs = msgs + [{"role": "assistant", "content": reaction.get("content", "")}]
            
            text = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in msgs])
            entities = await self.entity_extractor.extract_entities(text)
            
            for ent in entities:
                entity = ent.get("entity")
                key = ent.get("key")
                val = ent.get("value")
                if entity and key and val:
                    self.hippo.upsert_fact(session_id, entity, key, val, trace_id=trace_id)
        except Exception as e:
            logger.warning(f"[ROUTER] Entity extraction worker fail: {e}")

    async def distill_session(self, session_id: str) -> str:
        await self._auto_distill_worker(session_id)
        return self.neo.get_summary(session_id)

    async def _vault_scan_loop(self):
        while self.vault_indexer:
            try:
                if self.vault_indexer.index_all()["indexed"] > 0: logger.info("Vault Indexed.")
            except: pass
            await asyncio.sleep(300)

    async def nudge(self):
        """v0.2.1: Force the brain to breathe immediately (useful for testing)."""
        self._nudge_event.set()

    async def breathe(self):
        """v0.2.1: Execute one cycle of memory processing."""
        # 1. Process pending entity extractions
        if self._pending_trace_extractions:
            to_process = self._pending_trace_extractions[:]
            self._pending_trace_extractions = []
            logger.info(f"[BREATHE] Processing {len(to_process)} pending extractions.")
            for sid, tid in to_process:
                await self._auto_entity_worker(sid, tid)
                await asyncio.sleep(0.5) # Breather to avoid LLM overload
        # 2. Process dirty sessions (Distillation)
        if self._dirty_sessions:
            to_distill = list(self._dirty_sessions)
            self._dirty_sessions.clear()
            logger.debug(f"[BREATHE] Distilling dirty sessions: {to_distill}")
            for sid in to_distill:
                logger.info(f"[BREATHE] Distilling session: {sid}")
                await self._auto_distill_worker(sid)
                await asyncio.sleep(0.01)

    async def _cognitive_heartbeat_loop(self):
        """v0.2: The Breathing Brain - Autonomous background processing."""
        logger.info(f"[ROUTER] Cognitive heartbeat started (Interval: {self.heartbeat_interval}s)")
        while True:
            try:
                # Wait for interval OR manual nudge
                try:
                    await asyncio.wait_for(self._nudge_event.wait(), timeout=self.heartbeat_interval)
                except asyncio.TimeoutError:
                    pass # Regular interval reached
                
                self._nudge_event.clear()
                await self.breathe()
                await asyncio.sleep(0) # Yield control
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HEARTBEAT] Loop error: {e}")

    async def aclose(self):
        logger.info("[ROUTER] Closing memory engine connections...")
        clear_chroma_clients()
