# Generated from design/memory_pageindex.md v1.2
import os
import json
import hashlib
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from src.utils.llm_client import LLMFactory, LLMClient

logger = logging.getLogger("GATEWAY.MEMORY.PAGEINDEX")

class PageNode:
    def __init__(self, node_id: str, title: str, content: str, page_range: Tuple[int, int]):
        self.id = node_id
        self.title = title
        self.content = content
        self.summary = ""
        self.page_range = page_range
        self.children: List['PageNode'] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "page_range": list(self.page_range),
            "children": [c.to_dict() for c in self.children]
        }

class PageIndexer:
    """
    PageIndex Implementation: Vectorless, Reasoning-Based RAG.
    v1.2: Fully decoupled via LLMFactory for unified cross-platform compatibility.
    """
    def __init__(self, db_dir: Path, distill_url: str, distill_model: str, distill_provider: str):
        self.db_dir = Path(db_dir)
        self.index_dir = self.db_dir / "pageindex"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        # v1.2: Use the standard LLM Abstraction Layer
        self.llm = LLMFactory.get_client(
            provider=distill_provider,
            url=distill_url,
            model=distill_model,
            timeout=90.0 # High-precision reasoning requires patience
        )
        
        # Concurrency Gate
        self.semaphore = asyncio.Semaphore(2)

    def _get_file_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    async def build_tree(self, file_path: Path) -> str:
        """Parses markdown structure and generates hierarchical summaries."""
        content = file_path.read_text()
        file_hash = self._get_file_hash(content)
        index_file = self.index_dir / f"{file_hash}.json"
        
        if index_file.exists():
            return file_hash

        logger.info(f"[PAGEINDEX] Building reasoning tree for {file_path.name}...")
        root = PageNode("root", file_path.name, content, (1, 1))
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("#"):
                title = line.strip("# ").strip()
                new_node = PageNode(f"node_{i}", title, "", (1, 1))
                root.children.append(new_node)
        
        await self._summarize_recursive(root)
        index_file.write_text(json.dumps(root.to_dict(), indent=2))
        return file_hash

    async def _summarize_recursive(self, node: PageNode):
        """Uses unified LLM client to summarize node content."""
        text = node.content[:2000] if node.content else f"Section: {node.title}"
        
        async with self.semaphore:
            try:
                # v1.2: Standardized generation call
                summary = await self.llm.generate(
                    prompt=f"Summarize this document section precisely for future retrieval:\n\n{text}",
                    system="You are a professional technical document indexer."
                )
                if summary and "[Error]" not in summary:
                    node.summary = summary.strip()
                else:
                    node.summary = f"Summary of {node.title}"
            except Exception as e:
                logger.error(f"[PAGEINDEX] Summary fail for {node.title}: {e}")
                node.summary = f"Summary of {node.title}"

        # Recurse
        tasks = [self._summarize_recursive(child) for child in node.children]
        if tasks: await asyncio.gather(*tasks)

    async def reasoning_search(self, query: str, file_hash: str) -> str:
        """Traverses the tree using reasoning traversal."""
        index_file = self.index_dir / f"{file_hash}.json"
        if not index_file.exists(): return ""
        
        tree = json.loads(index_file.read_text())
        choices = [f"[{i}] {c['title']}: {c['summary']}" for i, c in enumerate(tree.get("children", []))]
        if not choices: return ""

        prompt = (
            f"USER QUERY: '{query}'\n\n"
            "AVAILABLE SECTIONS:\n" + "\n".join(choices) + "\n\n"
            "INSTRUCTION: Which section index is most relevant to answering the query? "
            "Respond ONLY with the index number (e.g. 0)."
        )
        
        async with self.semaphore:
            try:
                result = await self.llm.generate(prompt=prompt, system="You are a precision navigation agent.")
                # Extract digit
                match = re.search(r'\d+', result)
                if match:
                    idx = int(match.group())
                    if idx < len(tree["children"]):
                        target = tree["children"][idx]
                        logger.info(f"[PAGEINDEX] Reasoned navigation to: {target['title']}")
                        return f"EXACT SOURCE ({target['title']}): {target['summary']}"
            except Exception as e:
                logger.error(f"[PAGEINDEX] Traversal fail: {e}")
        
        return ""
