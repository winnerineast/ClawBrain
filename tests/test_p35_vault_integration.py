# Generated from design/memory_vault.md v1.0
import pytest
import os
import shutil
import asyncio
import time
from pathlib import Path
from src.memory.router import MemoryRouter
from src.memory.storage import clear_chroma_clients
from tests.vault_generator import VaultGenerator

def visual_audit(test_name, step, expected, actual):
    match = "YES" if str(expected) == str(actual) else "NO"
    print(f"\n[VAULT AUDIT: {test_name}]")
    print(f"STEP: {step}")
    print("-" * 70)
    print(f"{'EXPECTED':<33} | {'ACTUAL'}")
    print(f"{str(expected)[:33]:<33} | {str(actual)[:33]}")
    print("-" * 70)
    print(f"MATCH: {match}")
    print("=" * 70)

@pytest.mark.asyncio
async def test_p35_vault_change_detection_matrix(tmp_path):
    """
    Verifies the mtime + hash logic across all quadrants of the matrix.
    STRICT SEQUENTIAL EXECUTION.
    """
    clear_chroma_clients()
    db_dir = tmp_path / "db"
    vault_dir = tmp_path / "vault"
    db_dir.mkdir()
    vault_dir.mkdir()
    
    # 1. Setup mock vault
    gen = VaultGenerator()
    gen.setup_hardened_mock(str(vault_dir))
    
    # 2. Initialize Router with AUTO-SCAN DISABLED to ensure order
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    router = MemoryRouter(db_dir=str(db_dir), enable_room_detection=False, enable_auto_scan=False)
    await router.wait_until_ready()
    
    # TC_ZERO: Initial Scan (Manual)
    stats = await router.vault_indexer.scan()
    visual_audit("TC_ZERO", "Initial full index", "4 indexed", f"{stats['indexed']} indexed")
    assert stats["indexed"] == 4
    
    # TC_STALE: Idle scan (Manual)
    stats = await router.vault_indexer.scan()
    visual_audit("TC_STALE", "No changes", "0 indexed, 4 skipped", f"{stats['indexed']} indexed, {stats['skipped']} skipped")
    assert stats["indexed"] == 0
    assert stats["skipped"] == 4
    
    # TC_TOUCH: touch -m (metadata change, content same)
    target_file = str(vault_dir / "root_note.md")
    # Small sleep to ensure mtime definitely changes
    time.sleep(0.1)
    gen.touch_file(target_file, time.time())
    
    stats = await router.vault_indexer.scan()
    visual_audit("TC_TOUCH", "mtime changed, hash same", "0 indexed, 1 hash checked", 
                 f"{stats['indexed']} indexed, {stats['hash checked']} hash checked")
    assert stats["indexed"] == 0
    assert stats["hash checked"] == 1
    
    # TC_REAL: Real content change
    gen.create_note(str(vault_dir), "root_note.md", "# Root Note\nUpdated content for TC_REAL.")
    stats = await router.vault_indexer.scan()
    visual_audit("TC_REAL", "Content changed", "1 indexed", f"{stats['indexed']} indexed")
    assert stats["indexed"] == 1

@pytest.mark.asyncio
async def test_p35_vault_retrieval_priority(tmp_path):
    """Verifies that vault knowledge is retrieved semantically and placed correctly."""
    clear_chroma_clients()
    db_dir = tmp_path / "db"
    vault_dir = tmp_path / "vault"
    db_dir.mkdir()
    vault_dir.mkdir()
    
    gen = VaultGenerator()
    gen.create_note(str(vault_dir), "secrets.md", "# Secrets\nThe master password is 'ORION-99'.")
    
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    # Disable auto-scan to control indexing time
    router = MemoryRouter(db_dir=str(db_dir), enable_room_detection=False, enable_auto_scan=False)
    await router.wait_until_ready()
    await router.vault_indexer.scan()
    
    # Query
    context = await router.get_combined_context("session-vault", "What is the primary password?")
    
    assert "ORION-99" in context
    assert "=== EXTERNAL KNOWLEDGE (VAULT) ===" in context
