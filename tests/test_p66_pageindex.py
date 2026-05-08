# Generated from design/memory_pageindex.md v1.0
import pytest
import os
import asyncio
from pathlib import Path
from src.memory.router import MemoryRouter

@pytest.mark.asyncio
async def test_pageindexer_tree_generation(tmp_path):
    """Verify that PageIndexer builds a hierarchical tree for a large file."""
    db_dir = tmp_path / "db"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    
    # Create a complex markdown file > 5000 chars
    large_content = "# System Overview\n" + "Introduction to the platform.\n" * 100
    large_content += "\n## Power Specifications\n" + "Voltage: 12V DC.\n" * 50
    large_content += "\n## Network Configuration\n" + "IP: 192.168.1.1\n" * 50
    
    manual_path = vault_dir / "Manual.md"
    manual_path.write_text(large_content)
    
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    router = MemoryRouter(db_dir=db_dir)
    await router.wait_until_ready()
    
    # Trigger scan
    stats = await router.vault_indexer.scan()
    assert stats["indexed"] == 1
    
    # Trigger deep indexing manually (normally background)
    await router.page_indexer.build_tree(manual_path)
    
    # Check if tree exists
    index_files = list((db_dir / "pageindex").glob("*.json"))
    assert len(index_files) == 1
    
    # Verify tree structure
    import json
    tree = json.loads(index_files[0].read_text())
    assert tree["title"] == "Manual.md"
    assert len(tree["children"]) >= 3 # Root + headers
    
    await router.aclose()

@pytest.mark.asyncio
async def test_hybrid_routing_pageindex(tmp_path):
    """Verify that complex queries trigger PageIndex reasoning."""
    db_dir = tmp_path / "db"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    
    large_content = "# Project Alpha\nThis is a long document.\n" * 300
    large_content += "\n## Technical Parameters\nTarget voltage for high altitude: 48V."
    
    manual_path = vault_dir / "Alpha_Specs.md"
    manual_path.write_text(large_content)
    
    # Setup router with vault
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    router = MemoryRouter(db_dir=db_dir)
    await router.wait_until_ready()
    
    # Build tree
    await router.vault_indexer.scan()
    await router.page_indexer.build_tree(manual_path)
    
    # Complex query containing keywords
    query = "What is the technical parameter for voltage in high altitude?"
    context = await router.get_combined_context("test_session", query)
    
    # Verify PageIndex was triggered and successful
    assert "DEEP MINED: Alpha_Specs.md" in context
    assert "48V" in context
    
    # Check event log
    events = [e for e in router._cognitive_events if e["type"] == "DeepMining"]
    assert len(events) > 0
    
    await router.aclose()
