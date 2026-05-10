# Generated from design/memory_pageindex.md v1.0 / Issue #48
import pytest
import os
import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from src.memory.router import MemoryRouter
from src.utils.llm_client import EmbedClient

class DummyEmbedClient(EmbedClient):
    def __init__(self):
        super().__init__("http://dummy", "dummy")
    def _embed(self, texts):
        results = []
        for text in texts:
            vec = [0.0] * 384
            for char in text.lower():
                vec[ord(char) % 384] += 1.0
            mag = sum(v*v for v in vec) ** 0.5
            if mag > 0: vec = [v/mag for v in vec]
            results.append(vec)
        return results
    async def embed(self, texts, **kwargs): return self._embed(texts)
    def embed_sync(self, texts, **kwargs): return self._embed(texts)

@pytest.mark.asyncio
async def test_pageindexer_tree_generation(tmp_path):
    """验证 PageIndexer 能够为大文件构建层级树。"""
    db_dir = tmp_path / "db"
    vault_dir = tmp_path / "vault"
    db_dir.mkdir(); vault_dir.mkdir()
    
    large_content = "# System Overview\n" + "Intro content.\n" * 10
    large_content += "\n## Power Specs\n" + "Voltage: 12V DC.\n" * 5
    manual_path = vault_dir / "Manual.md"; manual_path.write_text(large_content)
    
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    
    # 模拟 Scheduler 和 Client
    mock_scheduler = MagicMock()
    mock_client = AsyncMock()
    mock_client.generate.return_value = "Mocked Summary"
    mock_client.model = "mock-model"
    mock_scheduler.select_best_chat.return_value = mock_client
    
    # 注意：PageIndexer 内部会调用 get_intelligent_scheduler
    with patch("src.utils.llm_client.LLMFactory.get_intelligent_scheduler", return_value=mock_scheduler):
        router = MemoryRouter(db_dir=str(db_dir), embed_client=DummyEmbedClient())
        await router.wait_until_ready()
        
        await router.vault_indexer.scan()
        await router.page_indexer.build_tree(manual_path)
        
        index_files = list((db_dir / "pageindex").glob("*.json"))
        assert len(index_files) == 1
        
        tree = json.loads(index_files[0].read_text())
        assert tree["title"] == "Manual.md"
        assert len(tree["children"]) >= 1
        await router.aclose()

@pytest.mark.asyncio
async def test_hybrid_routing_pageindex(tmp_path):
    """验证复杂查询能够触发 PageIndex 推理。"""
    db_dir = tmp_path / "db"
    vault_dir = tmp_path / "vault"
    db_dir.mkdir(); vault_dir.mkdir()
    
    content = "# Alpha Project\n## Technical Parameters\nTarget voltage is 48V."
    manual_path = vault_dir / "Alpha.md"; manual_path.write_text(content)
    
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    os.environ["CLAWBRAIN_DISABLE_COGNITIVE_JUDGE"] = "true"

    mock_scheduler = MagicMock()
    mock_client = AsyncMock()
    mock_client.model = "mock-model"
    # 第一次调用返回摘要，第二次调用返回索引 "0"
    mock_client.generate.side_effect = ["Summary A", "Summary B", "Summary Root", "0"]
    mock_scheduler.select_best_chat.return_value = mock_client
    
    with patch("src.utils.llm_client.LLMFactory.get_intelligent_scheduler", return_value=mock_scheduler):
        router = MemoryRouter(db_dir=str(db_dir), embed_client=DummyEmbedClient())
        await router.wait_until_ready()
        
        await router.vault_indexer.scan()
        await router.page_indexer.build_tree(manual_path)
        
        # 包含 "voltage" 关键词，应触发 PageIndex
        query = "What is the voltage?"
        context = await router.get_combined_context("session-66", query)
        
        print(f"\n[ISSUE-48 AUDIT] Context: {context}")
        assert "EXACT SOURCE" in context
        await router.aclose()
