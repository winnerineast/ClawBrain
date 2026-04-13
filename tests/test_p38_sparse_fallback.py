import pytest
import os
import shutil
import asyncio
from src.memory.router import MemoryRouter
from src.memory.storage import clear_chroma_clients

@pytest.mark.asyncio
async def test_sparse_fallback_logic(tmp_path):
    """
    Verify that when semantic search fails (sparse data), 
    the fallback keyword search finds the fact.
    """
    clear_chroma_clients()
    db_dir = str(tmp_path)
    router = MemoryRouter(db_dir=db_dir, enable_room_detection=False)
    await router.wait_until_ready()
    
    session_id = "sparse-test-session"
    fact_content = "The ultra-secret-code is MAGENTA-OWL-42"
    
    # 1. Ingest fact
    await router.ingest({"messages": [{"role": "user", "content": fact_content}]}, context_id=session_id)
    
    # 2. Query with a keyword that might fail semantic similarity in a cold start
    # but should definitely hit the fallback substring match.
    query = "ultra-secret-code"
    
    context = await router.get_combined_context(session_id, query)
    
    print(f"\n[SPARSE FALLBACK TEST] Query: '{query}'")
    print(f"Context Output:\n{context}")
    
    assert "MAGENTA-OWL-42" in context
    assert "RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS)" in context
