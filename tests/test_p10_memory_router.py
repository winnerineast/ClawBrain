# Generated from design/memory_router.md v1.0
import pytest
import json
import os
import shutil
from pathlib import Path
from src.memory.router import MemoryRouter

TEST_DIR = "/home/nvidia/ClawBrain/tests/data/p10_marathon_tmp"

def visual_audit_marathon(test_name, description, expected, actual):
    match = "YES" if str(expected).lower() in str(actual).lower() else "NO"
    print(f"\n[NEURAL MARATHON AUDIT: {test_name}]")
    print("=" * 80)
    print(f"SCENARIO: {description}")
    print("-" * 80)
    print(f"{'EXPECTED KNOWLEDGE':<38} | {'ACTUAL RECALL'}")
    print(f"{'-'*38} | {'-'*38}")
    print(f"{str(expected)[:38]:<38} | {str(actual)[:38]}...")
    print("-" * 80)
    print(f"INTEGRITY MATCH: {match}")
    print("=" * 80)

@pytest.mark.asyncio
async def test_p10_marathon_pressure_and_recall():
    """Phase 10 强化审计：50轮对话、1MB冲击、7天跨度的全链路验收"""
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    router = MemoryRouter(db_dir=TEST_DIR)
    
    # 1. 加载强化数据集
    data = json.loads(Path("tests/data/p10_marathon.json").read_text())
    thread = data["marathon_thread"]
    canary = data["canaries"]["initial_protocol"]
    
    print(f"\n[MARATHON START] Ingesting {len(thread)} interactions...")
    
    # 2. 模拟真实摄入流
    for msg in thread[:-1]: # 摄入除最后一条外的所有历史
        payload = {
            "model": "gemma4:e4b",
            "messages": [msg]
        }
        await router.ingest(payload)
    
    # 3. 验证 1MB 冲击后的系统状态
    # 检查磁盘是否有 Blob 生成
    blob_count = len(list(Path(TEST_DIR).glob("blobs/*.json")))
    print(f"  - Impact Check: {blob_count} blobs persisted to disk.")
    assert blob_count > 0
    
    # 4. 执行长程召回测试 (提问 7 天前的内容)
    current_focus = "initial protocol version"
    context = await router.get_combined_context("session-marathon", current_focus)
    
    # 执行高保真审计
    visual_audit_marathon(
        "7-Day Temporal Recall",
        "Recalling Canary Fact from Round 1 after 50 rounds + 1MB data shock",
        canary,
        context
    )
    
    # 核心断言：金丝雀事实必须在合成后的上下文（无论是 L2 检索还是 L3 摘要）中浮现
    assert canary.lower() in context.lower()
    assert "RELEVANT HISTORICAL SNIPPETS" in context
