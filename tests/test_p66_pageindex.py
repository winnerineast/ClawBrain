# Generated from design/memory_pageindex.md v1.0
import pytest
import os
import asyncio
import hashlib
import json
from pathlib import Path
from src.memory.router import MemoryRouter
from src.utils.llm_client import LLMFactory

@pytest.mark.asyncio
async def test_pageindexer_tree_generation_real(tmp_path):
    """
    [NO-MOCK] Verify that PageIndexer builds a hierarchical tree using the REAL local LLM.
    """
    db_dir = tmp_path / "db"
    vault_dir = tmp_path / "vault"
    db_dir.mkdir(); vault_dir.mkdir()
    
    # Create a complex markdown file > 5000 chars to trigger deep indexing
    large_content = "# System Overview\n" + "This platform provides a neural relay for AI memory.\n" * 20
    large_content += "\n## Component A: The Relay\n" + "Handles real-time traffic and proxying.\n" * 10
    large_content += "\n## Component B: The Brain\n" + "Handles background distillation and reasoning.\n" * 10
    
    manual_path = vault_dir / "System_Spec.md"
    manual_path.write_text(large_content)
    
    # Setup environment for the router
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    
    router = MemoryRouter(db_dir=str(db_dir))
    await router.wait_until_ready()
    
    # 1. Trigger vault scan to detect the new file
    await router.vault_indexer.scan()
    
    # 2. Trigger PageIndex build tree (This will call the real local LLM)
    # Note: We call it directly here to verify success, although the scan loop would also trigger it.
    file_hash = await router.page_indexer.build_tree(manual_path)
    assert file_hash != ""
    
    # 3. Verify JSON persistence
    index_files = list((db_dir / "pageindex").glob("*.json"))
    assert len(index_files) == 1
    
    tree = json.loads(index_files[0].read_text())
    assert tree["title"] == "System_Spec.md"
    assert len(tree["children"]) >= 2
    assert tree["summary"] != ""
    assert "[FAILED_INDEX]" not in tree["summary"]
    
    print(f"\n[PAGEINDEX REAL AUDIT] Tree built successfully for {tree['title']}")
    print(f"Summary: {tree['summary'][:100]}...")
    
    await router.aclose()

@pytest.mark.asyncio
async def test_hybrid_routing_pageindex_real(tmp_path):
    """
    [NO-MOCK] Verify that complex queries trigger PageIndex reasoning using the REAL local LLM.
    """
    db_dir = tmp_path / "db"
    vault_dir = tmp_path / "vault"
    db_dir.mkdir(); vault_dir.mkdir()
    
    # Precise fact in a large file
    content = "# Project X Technical Manual\n" + "Filler text to make the file large enough.\n" * 150
    content += "\n## Critical Parameters\n"
    content += "The maximum operating temperature for the main CPU is **85.5C**."
    
    manual_path = vault_dir / "ProjectX.md"
    manual_path.write_text(content)
    
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    os.environ["CLAWBRAIN_DISABLE_COGNITIVE_JUDGE"] = "true" # Focus on retrieval, not judge
    
    router = MemoryRouter(db_dir=str(db_dir))
    await router.wait_until_ready()
    
    # Indexing
    await router.vault_indexer.scan()
    await router.page_indexer.build_tree(manual_path)
    
    # Complex query containing keywords to trigger PageIndex
    query = "What is the maximum operating temperature for the CPU in Project X?"
    context = await router.get_combined_context("session-real-test", query)
    
    print(f"\n[HYBRID ROUTER REAL AUDIT] Query: {query}")
    print(f"Enriched Context Result: {context}")
    
    # Assertions
    assert "EXACT SOURCE" in context
    assert "85.5" in context
    
    await router.aclose()
