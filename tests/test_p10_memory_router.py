# Generated from design/memory_router.md v1.5
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
    print("-" * 60)
    print(f"INTEGRITY MATCH: {match}")
    print("=" * 80)

@pytest.mark.asyncio
async def test_p10_marathon_pressure_and_recall():
    """Phase 10 强化审计：4.5MB 真实文档冲击下的全链路验收"""
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    router = MemoryRouter(db_dir=TEST_DIR)
    
    # 1. 加载强化数据集
    data_path = Path("tests/data/p10_marathon.json")
    data = json.loads(data_path.read_text())
    thread = data["marathon_thread"]
    
    # 3.2 准则：使用 secure_protocol 作为 Key
    canary = data["canaries"]["secure_protocol"]
    
    print(f"\n[MARATHON START] Ingesting {len(thread)} interactions...")
    
    # 2. 模拟真实摄入流
    for msg in thread:
        payload = {
            "model": "gemma4:e4b",
            "messages": [msg]
        }
        await router.ingest(payload)
    
    # 3.1 准则：验证 4MB+ 冲击后的系统状态
    blob_count = len(list(Path(TEST_DIR).glob("blobs/*.json")))
    # 获取 Blob 文件大小
    blobs = list(Path(TEST_DIR).glob("blobs/*.json"))
    actual_size = os.path.getsize(blobs[0]) if blobs else 0
    
    print(f"  - Impact Check: {blob_count} blobs persisted.")
    print(f"  - Actual Blob Size: {actual_size} bytes")
    
    # 验证点：必须确切触发分流
    assert blob_count > 0
    assert actual_size > 512 * 1024
    
    # 4. 执行长程召回测试
    context = await router.get_combined_context("marathon-session", "secure protocol version")
    
    visual_audit_marathon(
        "4.5MB Impact & Recall",
        "Verification of Blob offloading (>512KB) and Canary Recall",
        canary,
        context
    )
    
    assert canary.lower() in context.lower()
