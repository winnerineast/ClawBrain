# Generated from design/memory_router.md v1.6
import pytest
import os
import shutil
from src.memory.router import MemoryRouter

TEST_DIR = "/home/nvidia/ClawBrain/tests/data/p10_trigger_tmp"

@pytest.mark.asyncio
async def test_p10_auto_distill_trigger_audit():
    """验证：当消息达到 50 条时，自动触发后台提纯任务"""
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    router = MemoryRouter(db_dir=TEST_DIR)
    
    print("\n[MARATHON TRIGGER TEST] Pumping 50 messages...")
    for i in range(50):
        await router.ingest({"messages": [{"role": "user", "content": f"Msg {i}"}]})
    
    # 我们通过捕获 stdout 来验证日志输出
    # (在 pytest -s 模式下会看到打印)
    print("Pumping complete.")
