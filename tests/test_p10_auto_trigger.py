# Generated from design/memory_router.md v1.10
import pytest
import os
import shutil
import asyncio
import sqlite3
from src.memory.router import MemoryRouter

TEST_DIR = "/home/nvidia/ClawBrain/tests/data/p10_trigger_tmp"
DB_PATH = os.path.join(TEST_DIR, "hippocampus.db")

@pytest.mark.asyncio
async def test_p10_auto_distill_trigger_audit():
    """验证：不仅触发 Worker，且新皮层确实产生了有效的摘要内容"""
    if os.path.exists(TEST_DB_DIR if 'TEST_DB_DIR' in locals() else TEST_DIR): 
        shutil.rmtree(TEST_DB_DIR if 'TEST_DB_DIR' in locals() else TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)
    
    router = MemoryRouter(db_dir=TEST_DIR, distill_threshold=50)
    
    print("\n[MARATHON TRIGGER TEST] Pumping 50 messages...")
    for i in range(50):
        # 泵入带语义的消息，以便产生更有意义的摘要
        await router.ingest({
            "context_id": "marathon_audit", 
            "messages": [{"role": "user", "content": f"Fact #{i}: The system component {i} is verified."}]
        })
    
    print("Pumping complete. Waiting 15s for LLM Distillation (NC_DIST)...")
    await asyncio.sleep(15.0)
    
    # 终极确证：穿透式数据库审计
    print("\n[DATABASE PENETRATION AUDIT]")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT summary_text FROM neocortex_summaries WHERE context_id='marathon_audit'")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        pytest.fail("AUDIT FAIL: No summary record found in neocortex_summaries table.")
    
    summary_text = row[0]
    print(f"Captured Summary: {summary_text[:150]}...")
    
    # 断言逻辑：非空、非错误
    assert len(summary_text) > 10, "Summary text is too short."
    assert not summary_text.startswith("[Error]"), f"Summary contains distillation error: {summary_text}"
    
    print("AUDIT SUCCESS: Real knowledge found in Neocortex.")
