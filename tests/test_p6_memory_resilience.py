# Generated from design/memory.md v1.7
import pytest
import asyncio
from src.memory.core import MemoryEngine, TraceStatus

def visual_audit(test_name, input_data, expected, actual):
    match = "YES" if str(expected) == str(actual) else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {str(input_data)[:100]}...")
    print("-" * 60)
    print(f"{'EXPECTED STATE':<27} | {'ACTUAL STATE'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected):<27} | {str(actual)}")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

@pytest.mark.asyncio
async def test_symmetric_commit_flow():
    """验证完整的 刺激-反应 对称提交链路"""
    engine = MemoryEngine()
    input_payload = {"model": "gemma4", "messages": [{"role": "user", "content": "Hi"}]}
    output_payload = {"message": {"role": "assistant", "content": "Hello"}}
    
    # 1. 录入输入
    tid = await engine.ingest_stimulus(input_payload)
    trace = engine.active_traces[tid]
    visual_audit("Stimulus Received", "User: Hi", TraceStatus.PENDING, trace.status)
    assert trace.status == TraceStatus.PENDING
    
    # 2. 录入响应
    await engine.associate_reaction(tid, output_payload)
    visual_audit("Reaction Committed", "Assistant: Hello", TraceStatus.COMMITTED, trace.status)
    assert trace.status == TraceStatus.COMMITTED
    assert trace.reaction == output_payload

@pytest.mark.asyncio
async def test_orphan_input_logic():
    """验证“孤儿输入”自动标记逻辑"""
    engine = MemoryEngine()
    input_payload = {"model": "gemma4", "messages": [{"role": "user", "content": "I will cancel this..."}]}
    
    # 录入输入后不给响应
    tid = await engine.ingest_stimulus(input_payload)
    
    # 模拟时间流逝（通过修改 trace 的 timestamp）
    engine.active_traces[tid].timestamp -= 600 
    
    # 执行清理
    engine.cleanup_orphans(ttl_seconds=300)
    
    orphan_trace = engine.working_memory[0]
    visual_audit("Orphan Intent Detection", "Cancelled Request", TraceStatus.ORPHAN, orphan_trace.status)
    assert orphan_trace.status == TraceStatus.ORPHAN
