# Generated from design/memory.md v1.8
import pytest
import json
from src.memory.core import MemoryEngine, TraceStatus
from src.memory.signals import SignalDecomposer

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
    """验证协议指纹的一致性"""
    payload1 = {"model": "gemma", "tools": ["read"], "messages": [{"content": "hi"}]}
    payload2 = {"model": "gemma", "tools": ["read"], "messages": [{"content": "different"}]}
    
    hash1 = SignalDecomposer.get_schema_fingerprint(payload1)
    hash2 = SignalDecomposer.get_schema_fingerprint(payload2)
    
    visual_audit("Schema Fingerprint Constancy", "Payload structure", hash1, hash2)
    # 虽然消息不同，但由于结构（model, tools）相同，Hash 必须一致
    assert hash1 == hash2

@pytest.mark.asyncio
async def test_core_intent_extraction():
    """验证最后一条 User 意图提取"""
    payload = {
        "messages": [
            {"role": "system", "content": "You are a bot"},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "Answer"},
            {"role": "user", "content": "The Real Goal"}
        ]
    }
    intent = SignalDecomposer.extract_core_intent(payload)
    visual_audit("Intent Extraction", "Multi-round messages", "The Real Goal", intent)
    assert intent == "The Real Goal"

@pytest.mark.asyncio
async def test_full_commit_flow():
    """验证对称提交"""
    engine = MemoryEngine()
    tid = await engine.ingest_stimulus({"q": "1"})
    await engine.associate_reaction(tid, {"a": "2"})
    status = engine.working_memory[0].status
    visual_audit("Commit Flow", "1 -> 2", TraceStatus.COMMITTED, status)
    assert status == TraceStatus.COMMITTED
