# Generated from design/memory_router.md v1.11
import pytest
import os
import shutil
from src.memory.router import MemoryRouter
from src.memory.signals import SignalDecomposer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = os.path.join(PROJECT_ROOT, "tests/data/p6_resilience_tmp")

def visual_audit(test_name, input_val, expected, actual):
    match = "YES" if str(expected) == str(actual) else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {repr(input_val)[:100]}...")
    print("-" * 60)
    print(f"{'EXPECTED':<27} | {'ACTUAL'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected)[:27]:<27} | {str(actual)[:27]}")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

@pytest.mark.asyncio
async def test_signal_fingerprinting():
    """Verify consistency of protocol fingerprints (Core Resilience)"""
    payload1 = {"model": "gemma", "tools": ["read"], "messages": [{"content": "hi"}]}
    payload2 = {"model": "gemma", "tools": ["read"], "messages": [{"content": "different"}]}
    
    hash1 = SignalDecomposer.get_schema_fingerprint(payload1)
    hash2 = SignalDecomposer.get_schema_fingerprint(payload2)
    
    visual_audit("Schema Fingerprint Constancy", "Payload structure", hash1, hash2)
    assert hash1 == hash2

@pytest.mark.asyncio
async def test_core_intent_extraction():
    """Verify extraction of the last User intent"""
    payload = {
        "messages": [
            {"role": "user", "content": "The Real Goal"}
        ]
    }
    intent = SignalDecomposer.extract_core_intent(payload)
    visual_audit("Intent Extraction", "The Real Goal", "The Real Goal", intent)
    assert intent == "The Real Goal"

@pytest.mark.asyncio
async def test_memory_router_ingest_resilience():
    """Verify L1/L2 dual activity after MemoryRouter ingestion"""
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    router = MemoryRouter(db_dir=TEST_DIR)
    await router.wait_until_ready()
    
    payload = {"context_id": "resilience", "messages": [{"role": "user", "content": "Keep this alive"}]}
    
    # 1. Ingest
    tid = await router.ingest(payload)
    
    # 2. Verify L1 (Working Memory) activity
    active_items = router._get_wm("default").get_active_contents()
    visual_audit("Working Memory Activity", "Ingest: Keep this alive", "True", "Keep this alive" in str(active_items))
    
    # 3. Verify L2 (Hippocampus) storage
    content = router.hippo.get_content(tid)
    visual_audit("Hippocampus Storage", "Trace ID: " + tid, "True", "Keep this alive" in str(content))
    
    assert "Keep this alive" in str(active_items)
    assert "Keep this alive" in str(content)
