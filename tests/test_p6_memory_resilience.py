# Generated from design/memory_router.md v1.11
import pytest
import os
import shutil
from src.memory.router import MemoryRouter
from src.memory.signals import SignalDecomposer

TEST_DIR = "/home/nvidia/ClawBrain/tests/data/p6_resilience_tmp"

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
    """验证协议指纹的一致性 (Core Resilience)"""
    payload1 = {"model": "gemma", "tools": ["read"], "messages": [{"content": "hi"}]}
    payload2 = {"model": "gemma", "tools": ["read"], "messages": [{"content": "different"}]}
    
    hash1 = SignalDecomposer.get_schema_fingerprint(payload1)
    hash2 = SignalDecomposer.get_schema_fingerprint(payload2)
    
    visual_audit("Schema Fingerprint Constancy", "Payload structure", hash1, hash2)
    assert hash1 == hash2

@pytest.mark.asyncio
async def test_core_intent_extraction():
    """验证最后一条 User 意图提取"""
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
    """验证 MemoryRouter 摄入后的 L1/L2 双重活性"""
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    router = MemoryRouter(db_dir=TEST_DIR)
    
    payload = {"context_id": "resilience", "messages": [{"role": "user", "content": "Keep this alive"}]}
    
    # 1. 摄入
    tid = await router.ingest(payload)
    
    # 2. 验证 L1 (Working Memory) 活性
    active_items = router._get_wm("default").get_active_contents()
    visual_audit("Working Memory Activity", "Ingest: Keep this alive", "True", "Keep this alive" in str(active_items))
    
    # 3. 验证 L2 (Hippocampus) 存储
    content = router.hippo.get_content(tid)
    visual_audit("Hippocampus Storage", "Trace ID: " + tid, "True", "Keep this alive" in str(content))
    
    assert "Keep this alive" in str(active_items)
    assert "Keep this alive" in str(content)
