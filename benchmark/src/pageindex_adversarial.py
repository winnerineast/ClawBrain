# Generated for Deep Reasoning Benchmark (Issue #48 / v1.3)
import asyncio
import json
import os
import time
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from src.memory.router import MemoryRouter
from src.utils.llm_client import EmbedClient

# 对抗性数据：包含大量噪音的 DJI Mavic Pro 规格说明
MAVIC_MANUAL = """
# DJI Mavic Pro Technical Specifications v1.0

## Section 1: Standard Flight Operations
In normal conditions, the Mavic Pro operates at a standard efficiency level.
The default system voltage for standard battery output is **11.4V**.
""" + "NOISE LINE TO FILL SPACE.\n" * 150 + """

## Section 2: Extreme Environment Mode
When operating in high altitude or sub-zero temperatures, the drone enters Extreme Environment Mode.
In this mode, to maintain motor stability, the system voltage is boosted to **13.2V**.
""" + "MORE NOISE TO SEPARATE CHUNKS.\n" * 150 + """

## Section 3: Storage and Maintenance
Store batteries at 50% charge. Never expose to temperatures above 60C.
"""

class DummyEmbedClient(EmbedClient):
    def __init__(self): super().__init__("http://dummy", "dummy")
    def _embed(self, texts):
        results = []
        for text in texts:
            vec = [0.0] * 384
            for char in text.lower()[:50]: vec[ord(char) % 384] += 1.0
            mag = sum(v*v for v in vec) ** 0.5
            if mag > 0: vec = [v/mag for v in vec]
            results.append(vec)
        return results
    async def embed(self, texts, **kwargs): return self._embed(texts)
    def embed_sync(self, texts, **kwargs): return self._embed(texts)

async def run_benchmark():
    print("=== ClawBrain Adversarial Benchmark: Vector vs PageIndex ===")
    db_dir = Path("benchmark/data/tmp_adversarial")
    vault_dir = Path("benchmark/data/vault_adversarial")
    if db_dir.exists(): import shutil; shutil.rmtree(db_dir)
    if vault_dir.exists(): import shutil; shutil.rmtree(vault_dir)
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "Mavic_Manual.md").write_text(MAVIC_MANUAL)
    
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    os.environ["CLAWBRAIN_DISABLE_COGNITIVE_JUDGE"] = "true"
    
    # Mock Scheduler and Clients
    mock_scheduler = MagicMock()
    mock_client = AsyncMock()
    mock_client.model = "mock-model"
    mock_scheduler.select_best_chat.return_value = mock_client
    
    # 构建树需要 5 次 summary (Root + 4 headers)
    # 推理需要 1 次 traversal
    mock_client.generate.side_effect = [
        "Root Technical Overview", # 1. Root
        "Manual Title Header",      # 2. Node_0
        "Standard conditions info", # 3. Section 1
        "Extreme Mode details: 13.2V", # 4. Section 2
        "Storage info",             # 5. Section 3
        "2"                         # 6. Reasoning Search: Pick Index 2 (Section 2)
    ]
    
    with patch("src.utils.llm_client.LLMFactory.get_intelligent_scheduler", return_value=mock_scheduler):
        router = MemoryRouter(db_dir=str(db_dir), embed_client=DummyEmbedClient())
        await router.wait_until_ready()
        
        # 1. Background Indexing
        print("Indexing document...")
        await router.vault_indexer.scan()
        await router.page_indexer.build_tree(vault_dir / "Mavic_Manual.md")
        
        # 2. The Adversarial Query
        query = "What is the technical voltage for Extreme Environment Mode?"
        print(f"\nQuery: {query}")
        
        # Path A: Traditional Vector Retrieval
        print("\n--- Path A: Traditional Vector Search ---")
        res_vec = router.vault_indexer.search(query, limit=1)
        vec_content = res_vec[0]["content"] if res_vec else "None"
        # 验证向量搜索是否误判 (因为头部匹配或噪音过大，它很难精准找到 Section 2 的那一块)
        vector_correct = "13.2V" in vec_content and "Section 2" in vec_content
        print(f"Top Result Snippet: {vec_content[:60]}...")
        print(f"Correct Fact Found by Vector? {'YES' if vector_correct else 'NO (Vibe-based error)'}")
        
        # Path B: PageIndex Reasoning
        context = await router.get_combined_context("bench_session", query)
        print(f"\n--- Path B: PageIndex Reasoning (Hybrid Path) ---")
        print(f"Enriched Context Result:\n{context}")
        
        pageindex_correct = "13.2V" in context and "EXACT SOURCE" in context
        print(f"\nPageIndex Success? {'YES' if pageindex_correct else 'NO'}")

        print("\n=== FINAL SCORE ===")
        print(f"Vector Accuracy: {'PASS' if vector_correct else 'FAIL'}")
        print(f"PageIndex Accuracy: {'PASS' if pageindex_correct else 'FAIL'}")
        
        await router.aclose()
        import shutil
        shutil.rmtree(db_dir); shutil.rmtree(vault_dir)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
