# Generated for Issue #48 Verification
import pytest
import asyncio
import respx
from httpx import Response
from pathlib import Path
import shutil
from src.memory.storage import Hippocampus, clear_chroma_clients
from src.utils.llm_client import OpenAIEmbedClient

@pytest.mark.asyncio
async def test_unified_embedding_engine(tmp_path):
    """
    验证 Hippocampus 能够使用注入的 OpenAIEmbedClient 进行同步嵌入。
    """
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    
    # 1. 模拟本地 Embedding 服务 (OpenAI 协议)
    mock_embedding = [0.1, 0.2, 0.3] * 128 # 384 维向量
    
    async with respx.mock:
        # 拦截嵌入请求
        respx.post("http://localhost:11434/v1/embeddings").mock(return_value=Response(
            200, 
            json={"data": [{"embedding": mock_embedding}]}
        ))

        # 2. 初始化 EmbedClient
        embed_client = OpenAIEmbedClient(url="http://localhost:11434", model="nomic-embed-text")
        
        # 3. 初始化 Hippocampus 并注入 EmbedClient
        clear_chroma_clients()
        hp = Hippocampus(db_dir=str(db_dir), embed_client=embed_client)
        
        # 4. 执行存储操作 (内部会触发同步嵌入)
        trace_id = "test-embed-48"
        payload = {"messages": [{"role": "user", "content": "Embedding Test"}]}
        hp.save_trace(trace_id, payload, search_text="Embedding Test")
        
        # 5. 执行检索操作 (内部也会触发同步嵌入)
        results = hp.search("Where is the embedding?")
        
        print(f"\n[ISSUE-48 AUDIT] Search Results: {results}")
        assert len(results) > 0
        assert trace_id in results

if __name__ == "__main__":
    import os
    import sys
    # 模拟 tmp_path 进行手动运行
    tmp = Path("/tmp/clawbrain_test_48")
    if tmp.exists(): shutil.rmtree(tmp)
    tmp.mkdir()
    asyncio.run(test_unified_embedding_engine(tmp))
