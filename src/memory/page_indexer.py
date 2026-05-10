# Generated from design/memory_pageindex.md v1.6
import os
import json
import hashlib
import logging
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from src.utils.llm_client import LLMScheduler, LLMFactory, ChatClient, HardwareProfiler

logger = logging.getLogger("GATEWAY.MEMORY.PAGEINDEX")

class PageNode:
    def __init__(self, node_id: str, title: str, content: str, page_range: Tuple[int, int]):
        self.id = node_id; self.title = title; self.content = content
        self.summary = ""; self.page_range = page_range
        self.children: List['PageNode'] = []

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "title": self.title, "summary": self.summary, "page_range": list(self.page_range), "children": [c.to_dict() for c in self.children]}

class PageIndexer:
    """
    PageIndex Implementation: Vectorless, Reasoning-Based RAG.
    v1.6: Fixed API parameter name (role instead of purpose).
    """
    def __init__(self, db_dir: Path, distill_url: str = None, distill_model: str = None, distill_provider: str = None):
        self.db_dir = Path(db_dir)
        self.index_dir = self.db_dir / "pageindex"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.scheduler = None; self.worker_client = None; self.brain_client = None
        # MANDATE: Force serialization (1) for large models to avoid empty responses.
        self.semaphore = asyncio.Semaphore(1)

    async def _ensure_scheduler(self):
        if not self.scheduler:
            self.scheduler = await LLMFactory.get_intelligent_scheduler()
            # FIX: Use 'role' as defined in LLMScheduler
            self.worker_client = self.scheduler.select_best_chat(role="worker")
            self.brain_client = self.scheduler.select_best_chat(role="brain")
            logger.info(f"🌿 [PAGEINDEX] Scheduler active. Worker: {self.worker_client.model}, Brain: {self.brain_client.model}")

    def _get_file_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    async def build_tree(self, file_path: Path) -> str:
        if not file_path.exists(): return ""
        await self._ensure_scheduler()
        raw_bytes = file_path.read_bytes(); file_hash = self._get_file_hash(raw_bytes)
        index_file = self.index_dir / f"{file_hash}.json"
        
        if index_file.exists():
            try:
                tree = json.loads(index_file.read_text())
                if tree.get("summary"): return file_hash
            except: pass

        logger.info(f"[PAGEINDEX] Building tree for {file_path.name}...")
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            try: import fitz; root = self._build_pdf_tree(file_path, raw_bytes, fitz)
            except: return ""
        else: root = self._build_markdown_tree(file_path, raw_bytes.decode(errors="ignore"))
        
        if not root: return ""
        await self._summarize_recursive(root)
        index_file.write_text(json.dumps(root.to_dict(), indent=2))
        return file_hash

    def _build_markdown_tree(self, file_path: Path, content: str) -> PageNode:
        root = PageNode("root", file_path.name, content[:1000], (1, 1))
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("#") and len(line) < 100:
                title = line.strip("# ").strip()
                snippet = "\n".join(lines[i:i+40])
                root.children.append(PageNode(f"node_{i}", title, snippet, (1, 1)))
        return root

    def _build_pdf_tree(self, file_path: Path, raw_bytes: bytes, fitz) -> Optional[PageNode]:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        root = PageNode("root", file_path.name, f"PDF with {len(doc)} pages.", (1, len(doc)))
        toc = doc.get_toc()
        if toc:
            for i, entry in enumerate(toc):
                lvl, title, page = entry
                if lvl <= 2:
                    next_page = toc[i+1][2] if i+1 < len(toc) else len(doc)
                    root.children.append(PageNode(f"pdf_{i}", title, doc[page-1].get_text()[:1500], (page, next_page)))
        doc.close(); return root

    async def _summarize_recursive(self, node: PageNode):
        """Zero Compromise: Real LLM summary. No head-truncation hacks."""
        if not node.content and not node.children: return
        text = node.content[:2000] if node.content else f"Section: {node.title}"
        summary = ""
        async with self.semaphore:
            for attempt in range(2):
                try:
                    res = await self.worker_client.generate(prompt=f"Summarize facts: {text}", system="You are a precise indexer.")
                    if res and "[Error]" not in res: 
                        summary = res.strip()
                        break
                except: pass
            
            # Mandate 13 & 14 Compliance: If it fails, it fails.
            if not summary:
                logger.error(f"[PAGEINDEX] Summary failed for {node.title} after 2 attempts.")
                summary = "[FAILED_INDEX]"
            
            node.summary = summary

        tasks = [self._summarize_recursive(child) for child in node.children]
        if tasks: await asyncio.gather(*tasks)

    async def reasoning_search(self, query: str, file_hash: str) -> str:
        index_file = self.index_dir / f"{file_hash}.json"
        if not index_file.exists(): return ""
        await self._ensure_scheduler()
        
        tree = json.loads(index_file.read_text())
        choices = [f"[{i}] {c['title']}: {c['summary'][:150]}" for i, c in enumerate(tree.get("children", []))]
        if not choices: return ""

        prompt = f"QUERY: {query}\nMAP:\n" + "\n".join(choices) + "\n\nPick the most relevant index number."
        async with self.semaphore:
            try:
                res = await self.brain_client.generate(prompt=prompt, system="You are a precision router. Respond ONLY with the number.")
                match = re.search(r'\d+', res)
                if match:
                    idx = int(match.group())
                    if idx < len(tree["children"]):
                        target = tree["children"][idx]
                        if "[FAILED_INDEX]" in target["summary"]: return ""
                        return f"EXACT SOURCE ({target['title']}): {target['summary']}"
            except: pass
        return ""
