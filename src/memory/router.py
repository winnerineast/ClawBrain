# Generated from design/memory_router.md v1.21 / GEMINI.md Rule 12
# Generated-by: 20260522-ISSUE-009-DesignSourceAlignment
import uuid
import json
import os
import asyncio
import logging
import time
import re
import hashlib
import platform
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
from src.memory.page_indexer import PageIndexer
from src.utils.config import get_env
from src.utils.llm_client import LLMFactory, ChatClient, EmbedClient, LLMScheduler

load_dotenv()

logger = logging.getLogger("GATEWAY.MEMORY.ROUTER")

class CircuitBreaker:
    def __init__(self, max_failures: int = 3, backoff_seconds: int = 60):
        self.max_failures = max_failures; self.backoff_seconds = backoff_seconds
        self.failures = 0; self.last_failure_time = 0
    def record_failure(self): self.failures += 1; self.last_failure_time = time.time()
    def record_success(self): self.failures = 0
    def is_open(self) -> bool:
        if self.failures >= self.max_failures:
            if time.time() - self.last_failure_time < self.backoff_seconds: return True
            self.failures = 0
        return False

class CognitiveWorker:
    def __init__(self, router: 'MemoryRouter'):
        self.router = router
        self.queue = asyncio.Queue()
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self._loop())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def enqueue(self, task_type: str, **kwargs):
        self.queue.put_nowait((task_type, kwargs))

    async def _loop(self):
        while True:
            try:
                task_type, kwargs = await self.queue.get()
                try:
                    if task_type == "topic_detection":
                        session_id = kwargs.get("session_id")
                        text = kwargs.get("text")
                        await self.router._auto_room_worker(session_id, text)
                    elif task_type == "distill":
                        session_id = kwargs.get("session_id")
                        await self.router._auto_distill_worker(session_id)
                    elif task_type == "vault_scan":
                        await self.router._run_vault_scan()
                    elif task_type == "build_tree":
                        path = kwargs.get("path")
                        if self.router.page_indexer:
                            await self.router.page_indexer.build_tree(path)
                except Exception as e:
                    logger.error(f"[COGNITIVE_WORKER] Error executing task {task_type}: {e}")
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[COGNITIVE_WORKER] Loop error: {e}")
                await asyncio.sleep(1)

class MemoryRouter:
    """
    ClawBrain Memory Central Router v2 (Breathing Brain).
    v1.19: Dynamic Path Resolution to fix Test Independence.
    """
    def __init__(self, db_dir: str, distill_url: str = None, distill_model: str = None, distill_provider: str = None, 
                 enable_room_detection: bool = True, distill_threshold: int = 50, enable_auto_scan: bool = True,
                 embed_client: EmbedClient = None):
        self.db_dir = Path(db_dir); self.ready_event = asyncio.Event()
        self.hippo = None; self.neo = None; self.room_detector = None
        self.vault_indexer = None; self.page_indexer = None; self.decomposer = None
        self.scheduler = None
        self.embed_client = embed_client
        
        self.distill_url = distill_url or get_env("CLAWBRAIN_DISTILL_URL", "http://127.0.0.1:11434")
        self.distill_model = distill_model or get_env("CLAWBRAIN_DISTILL_MODEL", "gemma4:e4b")
        self.distill_provider = distill_provider or get_env("CLAWBRAIN_DISTILL_PROVIDER", "ollama")
        
        self.distill_threshold = distill_threshold
        self.enable_room_detection = enable_room_detection
        self.enable_auto_distill = True; self.enable_auto_scan = enable_auto_scan
        self.enable_query_expansion = get_env("CLAWBRAIN_ENABLE_QUERY_EXPANSION", "true").lower() == "true"
        self.enable_late_stage_reranking = get_env("CLAWBRAIN_ENABLE_LATE_STAGE_RERANKING", "true").lower() == "true"
        
        self._wm_sessions: Dict[str, WorkingMemory] = {}
        self._current_rooms: Dict[str, str] = {}
        self._trace_counters: Dict[str, int] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._cognitive_events: List[Dict] = []
        self._dirty_sessions: set = set()
        self._heartbeat_seconds = 30 
        self._running = True
        self._integration_mode = "Standalone (Relay)"
        self._last_injections = {}
        
        vp = get_env("CLAWBRAIN_VAULT_PATH")
        self.vault_path = Path(vp) if vp else None

        self.cb_room = CircuitBreaker(); self.cb_distill = CircuitBreaker(); self.cb_heartbeat = CircuitBreaker()
        
        self.worker = CognitiveWorker(self)
        self.worker.start()
        
        asyncio.create_task(self._async_init())

    async def _async_init(self):
        try:
            logger.info(f"[COGNITIVE] Initializing Memory Engine at {self.db_dir}...")
            
            # P48: Discovered Embedding Support
            if not self.embed_client:
                self.scheduler = await LLMFactory.get_intelligent_scheduler()
                self.embed_client = await self.scheduler.select_best_chat(role="embedding")
            
            logger.info(f"🌿 [COGNITIVE] Using embedding model: {self.embed_client.model}")

            self.hippo = Hippocampus(str(self.db_dir), embed_client=self.embed_client)
            self.neo = Neocortex(db_dir=str(self.db_dir))
            self.room_detector = RoomDetector(url=self.distill_url, model=self.distill_model, provider=self.distill_provider)
            self.page_indexer = PageIndexer(db_dir=self.db_dir)
            self.decomposer = SignalDecomposer()
            
            if self.vault_path:
                self.vault_indexer = VaultIndexer(str(self.vault_path), self.db_dir, client=self.hippo.client, embed_client=self.embed_client)
                if self.enable_auto_scan: asyncio.create_task(self._vault_scan_loop())
            
            asyncio.create_task(self._heartbeat_loop())
            self._log_event("Cognitive", "System", "Intelligence layer stabilized and ready", {"platform": platform.system()})
            logger.info("[COGNITIVE] Intelligence stabilized.")
        except Exception as e: logger.exception(f"Initialization crash: {e}")
        finally: self.ready_event.set()

    async def wait_until_ready(self, timeout: float = 30.0):
        await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)

    def _log_event(self, plane: str, type: str, message: str, data: dict = None):
        event = {"timestamp": time.time(), "plane": plane, "type": type, "message": message, "data": data or {}}
        self._cognitive_events.append(event)
        if len(self._cognitive_events) > 1000: self._cognitive_events.pop(0)

    def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._session_locks: self._session_locks[session_id] = asyncio.Lock()
        return self._session_locks[session_id]

    def _get_wm(self, session_id: str) -> WorkingMemory:
        if session_id not in self._wm_sessions:
            wm = WorkingMemory(); self._wm_sessions[session_id] = wm
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
                            stim = p.get("stimulus", p); msgs = stim.get("messages", [])
                            for m in msgs:
                                if m.get("content"): wm.add_item(WorkingMemoryItem(trace_id=row["trace_id"], content=m["content"]))
            except Exception as e: logger.error(f"Hydration fail: {e}")
        return self._wm_sessions[session_id]

    def _get_current_room(self, session_id: str) -> str:
        return self._current_rooms.get(session_id, "general")

    async def _auto_room_worker(self, session_id: str, text: str):
        if self.cb_room.is_open(): return
        try:
            room = await self.room_detector.detect(text)
            if room and room != self._get_current_room(session_id):
                self._current_rooms[session_id] = room
                logger.info(f"[ROUTER] Topic shift detected in {session_id}: -> {room}")
            self.cb_room.record_success()
        except: self.cb_room.record_failure()

    async def ingest(self, stimulus: Dict[str, Any], session_id: str = "default", sync_distill: bool = False, offload_threshold: int = None, trace_id: str = None) -> str:
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            room_id = self._get_current_room(session_id); trace_id = trace_id or str(uuid.uuid4())
            search_text = " ".join([m.get("content", "") for m in stimulus.get("messages", []) if m.get("role") == "user"])
            wm = self._get_wm(session_id)
            for m in stimulus.get("messages", []):
                if m.get("content"): wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=m["content"]))
                
            # L6b Precision Value Filter: Filter out low value trace before persisting to database
            disable_judge = get_env("CLAWBRAIN_DISABLE_COGNITIVE_JUDGE", "false").lower() == "true"
            is_high_value = True
            if not disable_judge:
                try:
                    instruction = "You are a L6b Value Filter. Score the technical value of the conversation from 0.0 to 1.0. Respond ONLY with the float number."
                    score_str = await self.room_detector.llm.generate(prompt=search_text, system=instruction)
                    score_match = re.search(r"[0-9.]+", score_str or "1.0")
                    if score_match:
                        score = float(score_match.group(0))
                        if score < 0.5:
                            is_high_value = False
                except Exception as e:
                    logger.warning(f"[L6b] Value classification failed: {e}")

            if is_high_value:
                self.hippo.save_trace(trace_id, stimulus, search_text=search_text, session_id=session_id, room_id=room_id, threshold=offload_threshold)
            else:
                self.hippo.save_to_archive(trace_id, stimulus, session_id=session_id, room_id=room_id)
                self._log_event("Cognitive", "L6bFilter", f"Low value trace {trace_id} archived in SQLite by cognitive judge", {"session_id": session_id})

            self.hippo.save_wm_state(session_id, wm.items); self._dirty_sessions.add(session_id)
            
            if self.enable_room_detection: self.worker.enqueue("topic_detection", session_id=session_id, text=search_text)
            
            self._log_event("Relay", "Ingest", f"Captured user message for session {session_id}", {"session_id": session_id, "text": search_text[:50]})
            
            if sync_distill: await self._auto_distill_worker(session_id)
            return trace_id

    async def commit_turn(self, trace_id: str, payload: Dict[str, Any], reaction: Dict[str, Any], session_id: str, sync_distill: bool = False, offload_threshold: int = None):
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id); room_id = self._get_current_room(session_id)
            self.hippo.save_trace(trace_id, {"stimulus": payload, "reaction": reaction}, session_id=session_id, room_id=room_id, threshold=offload_threshold)
            if reaction.get("content"): wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=reaction["content"]))
            self.hippo.save_wm_state(session_id, wm.items); self._dirty_sessions.add(session_id)

    async def pre_turn_pending(self, stimulus: Dict[str, Any], session_id: str = "default") -> str:
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            trace_id = str(uuid.uuid4()); wm = self._get_wm(session_id)
            for m in stimulus.get("messages", []):
                if m.get("content"): wm.add_item(WorkingMemoryItem(trace_id=trace_id, content=m["content"]))
            self.hippo.save_trace(trace_id, {"stimulus": stimulus, "reaction": None}, session_id=session_id)
            self.hippo.save_wm_state(session_id, wm.items); return trace_id

    async def orphan_turn(self, trace_id: str, payload: Dict[str, Any], error: str, session_id: str = "default"):
        async with self._get_session_lock(session_id):
            self.hippo.save_trace(trace_id, {"stimulus": payload, "error": error}, session_id=session_id)

    async def get_combined_context(self, session_id: str, query: str, max_chars: int = None) -> str:
        if max_chars is None: max_chars = int(get_env("CLAWBRAIN_MAX_CONTEXT_CHARS", 2000))
        await self.wait_until_ready()
        async with self._get_session_lock(session_id):
            wm = self._get_wm(session_id)
            room_id = self._get_current_room(session_id)
            l3_summary = self.neo.get_summary(session_id, room_id=room_id) or ""
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

            # 1. Query Expansion
            queries = [query]
            if self.enable_query_expansion:
                try:
                    instruction = (
                        "You are a Search Assistant. Expand the user query into 2 alternative search formulations or synonyms, focusing on technical identifiers.\n"
                        "Respond with a JSON list of strings only, e.g. [\"formulation1\", \"formulation2\"]."
                    )
                    expanded_str = await self.neo.llm.generate(prompt=query, system=instruction)
                    match = re.search(r"\[\s*\"[^\"]*\"\s*(?:,\s*\"[^\"]*\"\s*)*\]", expanded_str or "")
                    if match:
                        expanded_queries = json.loads(match.group(0))
                        if isinstance(expanded_queries, list):
                            queries.extend([q for q in expanded_queries if q and isinstance(q, str)])
                except Exception as e:
                    logger.warning(f"[QUERY_EXPANSION] Query expansion failed: {e}")

            # 2. Retrieve L2 Hippocampus Memories
            cmap = {}
            lex_results = set()
            for q in queries:
                sem_res = self.hippo.search(q, session_id, room_id, limit=25, include_distances=True)
                for c in sem_res:
                    tid = c["id"]
                    dist = c["distance"]
                    if tid not in cmap or dist < cmap[tid]:
                        cmap[tid] = dist
                
                lex_ids = self.hippo.search_lexical(list(hard_anchors) + list(core_subjects)[:5], session_id, limit=25)
                lex_results.update(lex_ids)
                
            for lid in lex_results:
                if lid not in cmap: cmap[lid] = 1.0 
            
            reranked, seen = [], set()
            for tid, dist in cmap.items():
                p = self.hippo.get_full_payload(tid)
                if not p: continue
                stim = p.get("stimulus", p); msgs = stim.get("messages", [])
                txt = " | ".join([f"{m.get('role','user')}: {m.get('content','')}" for m in msgs]) if msgs else (stim.get("content") or stim.get("text") or str(stim))
                if not txt or txt in seen: continue 
                ok, sc = _is_satisfied(txt, dist)
                if ok: reranked.append({"content": txt, "score": sc}); seen.add(txt)

            reranked.sort(key=lambda x: x["score"], reverse=True)
            l2_contents = [it["content"] for it in reranked]
            if l2_contents:
                self._log_event("Cognitive", "MemorySearch", f"Semantic hit from Hippocampus (L2) for {session_id}", {"session_id": session_id, "count": len(l2_contents)})

            # 3. Retrieve Vault Memories
            vault_results = []
            if self.vault_indexer:
                seen_vault = set()
                for q in queries:
                    for r in self.vault_indexer.search(q, limit=5):
                        title = r["title"]
                        if title in seen_vault: continue
                        ok, sc = _is_satisfied(r["content"], r.get("distance", 1.0))
                        if ok:
                            vault_results.append({"title": title, "content": r["content"], "score": sc})
                            seen_vault.add(title)
                
                if vault_results:
                    logger.info(f"[RETRIEVAL AUDIT] {query} | VAULT_HIT: Y | {vault_results[0]['title']} | {vault_results[0]['score']}")
                else:
                    logger.info(f"[RETRIEVAL AUDIT] {query} | VAULT_HIT: N | None | 0.0")

                if vault_results:
                    self._log_event("Cognitive", "VaultSearch", f"Vault hit: {vault_results[0]['title']}", {"session_id": session_id, "count": len(vault_results)})

                    # PageIndex Integration: Trigger reasoning if confidence is low or query is complex
                    top_score = vault_results[0]["score"]
                    reasoning_keywords = ["compare", "parameter", "manual", "technical", "specification", "voltage", "temperature", "requirement", "configuration"]
                    is_complex = any(k in query.lower() for k in reasoning_keywords)

                    if (top_score < 0.7 or is_complex) and self.page_indexer and self.vault_path:
                        # Find the file hash to check if tree exists
                        for res in vault_results[:2]: # Try top 2 candidates
                            full_p = self.vault_path / res["title"]
                            if full_p.exists():
                                f_hash = hashlib.sha256(full_p.read_bytes()).hexdigest()
                                reasoning = await self.page_indexer.reasoning_search(query, f_hash)
                                if reasoning:
                                    self._log_event("Cognitive", "DeepMining", f"Reasoned from {res['title']}", {"session_id": session_id})
                                    # Logic Upgrade: Replace noisy search results with the precise fact
                                    vault_results = [{"title": f"DEEP MINED: {res['title']}", "content": reasoning, "score": 2.0}]
                                    break

                vault_results.sort(key=lambda x: x["score"], reverse=True)

            # 4. Cognitive Judge / Late-Stage Filtering
            disable_judge = get_env("CLAWBRAIN_DISABLE_COGNITIVE_JUDGE", "false").lower() == "true"
            filtered_l2_contents = list(l2_contents)
            filtered_vault_results = list(vault_results)
            
            if not disable_judge:
                if self.enable_late_stage_reranking:
                    # Select candidates: top 3 L2, top 2 Vault
                    candidate_snippets = []
                    mapping = []
                    
                    for idx, content in enumerate(l2_contents[:3]):
                        candidate_snippets.append(content)
                        mapping.append(("l2", idx))
                    for idx, r in enumerate(vault_results[:2]):
                        candidate_snippets.append(r["content"])
                        mapping.append(("vault", idx))
                        
                    if candidate_snippets:
                        relevant_indices = await self.neo.filter_relevant_snippets(query, candidate_snippets)
                        relevant_set = set(relevant_indices)
                        
                        temp_l2 = []
                        temp_vault = []
                        for c_idx, (t_type, orig_idx) in enumerate(mapping):
                            if c_idx in relevant_set:
                                if t_type == "l2":
                                    temp_l2.append(l2_contents[orig_idx])
                                else:
                                    temp_vault.append(vault_results[orig_idx])
                                    
                        # Admit remaining items beyond the evaluated ones as a safety margin
                        if len(l2_contents) > 3:
                            temp_l2.extend(l2_contents[3:])
                        if len(vault_results) > 2:
                            temp_vault.extend(vault_results[2:])
                            
                        filtered_l2_contents = temp_l2
                        filtered_vault_results = temp_vault
                else:
                    sample = "\n".join([l3_summary] + l2_contents[:1] + [r["content"] for r in vault_results[:1]])
                    is_truly_relevant = await self.neo.verify_relevance(query, sample)
                    if not is_truly_relevant:
                        filtered_l2_contents = []
                        filtered_vault_results = []

            if not any([l3_summary, filtered_vault_results, filtered_l2_contents]): 
                self._log_event("Relay", "ContextEnrichment", f"No relevant long-term memory for {session_id}", {"session_id": session_id, "gain": False})
                return ""
            
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
                    sec = ht + "\n".join(lines); output_parts.append(sec); cur_len += len(sec)

            if l3_summary: try_add("SYSTEM MEMORY SUMMARY (NEOCORTEX)", [l3_summary])
            try_add("ACTIVE CONVERSATION (WORKING MEMORY)", [it.content for it in working_items])
            if filtered_vault_results: try_add("EXTERNAL KNOWLEDGE (VAULT)", filtered_vault_results)
            try_add("RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS)", filtered_l2_contents, prefix="") 
            res = "[CLAWBRAIN MEMORY]" + "".join(output_parts)
            coupling = "\n\n[COGNITIVE COUPLING]: Cross-reference above facts. Prioritize NEOCORTEX."
            if len(res) + len(coupling) + 20 <= max_chars: res += coupling
            
            final_context = res + "\n[END CLAWBRAIN MEMORY]"
            self._log_event("Relay", "ContextEnrichment", f"Enriched context for {session_id} (+{len(final_context)} chars)", {
                "session_id": session_id,
                "sources": {"l3": bool(l3_summary), "l1": len(working_items), "vault": len(filtered_vault_results), "l2": len(filtered_l2_contents)}
            })
            return final_context

    async def nudge(self):
        """Manual trigger for the cognitive heartbeat (Regression Support)."""
        for sid in list(self._dirty_sessions):
            self.worker.enqueue("distill", session_id=sid)
        self._dirty_sessions.clear()
        await self.worker.queue.join()

    async def _heartbeat_loop(self):
        while self._running:
            if self.cb_heartbeat.is_open(): await asyncio.sleep(60); continue
            try:
                for sid in list(self._dirty_sessions):
                    self.worker.enqueue("distill", session_id=sid)
                self._dirty_sessions.clear(); self.cb_heartbeat.record_success()
            except Exception: self.cb_heartbeat.record_failure()
            await asyncio.sleep(30)

    async def _auto_distill_worker(self, session_id: str):
        if self.cb_distill.is_open(): return
        try:
            recent = self.hippo.get_recent_traces(limit=50, session_id=session_id)
            if recent:
                payloads = [self.hippo.get_full_payload(t["trace_id"]) for t in recent]
                room_id = self._get_current_room(session_id)
                await self.neo.distill(session_id, [p for p in payloads if p], room_id=room_id)
                self._log_event("Cognitive", "Distillation", f"L3 Neocortex consolidated for {session_id} in {room_id}", {"session_id": session_id, "room_id": room_id})
            self.cb_distill.record_success()
        except Exception: self.cb_distill.record_failure()

    async def _vault_scan_loop(self):
        while self._running and self.vault_indexer:
            self.worker.enqueue("vault_scan")
            await asyncio.sleep(300)

    async def _run_vault_scan(self):
        try:
            stats = await self.vault_indexer.scan()
            if stats.get("indexed", 0) > 0:
                self._log_event("Cognitive", "VaultScan", f"Vault indexed {stats['indexed']} new/updated files", stats)
                threshold = int(get_env("CLAWBRAIN_PAGEINDEX_THRESHOLD", 5000))
                for path_str in stats.get("modified_paths", []):
                    p = Path(path_str)
                    if p.suffix.lower() == ".pdf" or p.stat().st_size > threshold: 
                        self._log_event("Cognitive", "DeepIndexing", f"Building reasoning tree for {p.name}", {"path": str(p)})
                        self.worker.enqueue("build_tree", path=p)
        except Exception as e:
            logger.error(f"[COGNITIVE] Vault scan run error: {e}")

    async def aclose(self):
        self._running = False; logger.info("[ROUTER] Closing connections...")
        await self.worker.stop()
        clear_chroma_clients()
