# Generated from design/memory_pageindex.md v1.0
import os
import json
import hashlib
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from litellm import completion
from src.utils.config import get_env

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
    Transforms document hierarchy into a navigable reasoning tree.
    """
    def __init__(self, db_dir: Path, distill_url: str, distill_model: str, distill_provider: str):
        self.db_dir = db_dir
        self.index_dir = self.db_dir / "pageindex"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.url = distill_url
        self.model = distill_model
        self.provider = distill_provider
        
        # Mapping model to litellm format
        if self.provider == "ollama":
            self.llm_model = f"ollama/{self.model}"
            self.api_base = self.url
        elif self.provider == "openai":
            # For LM Studio or OMLX (OpenAI compatible)
            self.llm_model = f"openai/{self.model}"
            self.api_base = self.url
        else:
            self.llm_model = self.model
            self.api_base = self.url

    def _get_file_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    async def build_tree(self, file_path: Path) -> str:
        """Parses markdown structure and generates hierarchical summaries."""
        content = file_path.read_text()
        file_hash = self._get_file_hash(content)
        index_file = self.index_dir / f"{file_hash}.json"
        
        if index_file.exists():
            logger.info(f"[PAGEINDEX] Tree already exists for {file_path.name}")
            return file_hash

        logger.info(f"[PAGEINDEX] Building reasoning tree for {file_path.name}...")
        
        # Simple Markdown Header Parsing (Heuristic-based)
        root = PageNode("root", file_path.name, content, (1, 1)) # Dummy pages for MD
        lines = content.splitlines()
        
        # Construct flat hierarchy first
        current_node = root
        for i, line in enumerate(lines):
            if line.startswith("#"):
                level = line.count("#")
                title = line.strip("# ").strip()
                new_node = PageNode(f"node_{i}", title, "", (1, 1))
                root.children.append(new_node) # Simple flat for MVP
        
        # Recursive Summarization
        await self._summarize_recursive(root)
        
        index_file.write_text(json.dumps(root.to_dict(), indent=2))
        return file_hash

    async def _summarize_recursive(self, node: PageNode):
        """Uses LLM to summarize node content and its children."""
        # For MVP, we just summarize the whole block if no children
        text_to_summarize = node.content[:2000] if node.content else f"Section: {node.title}"
        
        try:
            resp = await asyncio.to_thread(
                completion,
                model=self.llm_model,
                messages=[{"role": "user", "content": f"Summarize this document section precisely for future retrieval:\n\n{text_to_summarize}"}],
                api_base=self.api_base,
                max_tokens=150
            )
            node.summary = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"[PAGEINDEX] Summarization failed: {e}")
            node.summary = f"Summary of {node.title}"

        for child in node.children:
            await self._summarize_recursive(child)

    async def reasoning_search(self, query: str, file_hash: str) -> str:
        """Traverses the tree to find the most relevant leaf node content."""
        index_file = self.index_dir / f"{file_hash}.json"
        if not index_file.exists(): return ""
        
        tree = json.loads(index_file.read_text())
        logger.info(f"[PAGEINDEX] Starting reasoning traversal for: {query[:30]}...")
        
        # Level 1 Traversal (MVP: Single level search)
        choices = []
        for i, child in enumerate(tree.get("children", [])):
            choices.append(f"[{i}] {child['title']}: {child['summary']}")
        
        prompt = f"Given the query: '{query}', which section index is most relevant?\n" + "\n".join(choices)
        prompt += "\n\nRespond with ONLY the index number (e.g., 0, 1, 2)."
        
        try:
            resp = await asyncio.to_thread(
                completion,
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                api_base=self.api_base,
                max_tokens=10
            )
            idx_str = "".join(filter(str.isdigit, resp.choices[0].message.content))
            if idx_str:
                idx = int(idx_str)
                if idx < len(tree["children"]):
                    target = tree["children"][idx]
                    logger.info(f"[PAGEINDEX] Navigated to section: {target['title']}")
                    # In real PageIndex, we would recurse. In MVP, we return the section's context.
                    return f"EXACT SOURCE ({target['title']}): {target['summary']}"
        except Exception as e:
            logger.error(f"[PAGEINDEX] Traversal failed: {e}")
        
        return ""
