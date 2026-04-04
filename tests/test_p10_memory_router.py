# Generated from design/memory_router.md v1.0
import pytest
import os
import shutil
from pathlib import Path
from src.memory.router import MemoryRouter

TEST_DIR = "/home/nvidia/ClawBrain/tests/data/p10_tmp"

def visual_audit_router(test_name, action, l1_status, l2_status, l3_status):
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"ACTION: {action}")
    print("-" * 60)
    print(f"{'LAYER':<27} | {'STATUS'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{'L1: Working Memory':<27} | {l1_status}")
    print(f"{'L2: Hippocampus':<27} | {l2_status}")
    print(f"{'L3: Neocortex':<27} | {l3_status}")
    print("-" * 60)
    print("=" * 60)

@pytest.mark.asyncio
async def test_p10_ingestion_routing():
    """验证摄入动作是否正确分发到 L1 和 L2"""
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    router = MemoryRouter(db_dir=TEST_DIR)
    
    payload = {"model": "test", "messages": [{"role": "user", "content": "Hello Router"}]}
    
    # 执行摄入
    tid = await router.ingest(payload)
    
    # 验证 L1 (Working Memory)
    l1_active = tid in [it.trace_id for it in router.wm.items]
    
    # 验证 L2 (Hippocampus)
    # 我们通过 FTS 搜索验证它是否已存入
    l2_stored = len(router.hippo.search("Hello Router")) > 0
    
    visual_audit_router(
        "Dual-Layer Ingestion",
        "Ingest 'Hello Router'",
        "ACTIVE" if l1_active else "MISSING",
        "STORED" if l2_stored else "MISSING",
        "N/A"
    )
    
    assert l1_active is True
    assert l2_stored is True

@pytest.mark.asyncio
async def test_p10_combined_context_synthesis():
    """验证三层记忆的复合合成逻辑"""
    router = MemoryRouter(db_dir=TEST_DIR)
    
    # 预置 L3 (Neocortex) 摘要
    router.neo._save_summary("session-1", "This user is interested in security.")
    
    # 预置 L1 (Working Memory)
    await router.ingest({"messages": [{"role": "user", "content": "Current question: SSH Keys"}]})
    
    # 执行合成
    context = await router.get_combined_context("session-1", "security")
    
    print(f"\n[SYNTHESIS PROOF]\n{context}\n")
    
    # 验证优先级和内容
    assert "SYSTEM MEMORY SUMMARY" in context
    assert "interested in security" in context
    assert "SSH Keys" in context
    
    visual_audit_router(
        "Context Synthesis",
        "Retrieve context for 'security'",
        "ACTIVE", "SEARCHED", "LOADED"
    )
