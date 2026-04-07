# Generated from design/memory_router.md v1.10
import pytest
import os
import shutil
import asyncio
import sqlite3
from src.memory.router import MemoryRouter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = os.path.join(PROJECT_ROOT, "tests/data/p10_trigger_tmp")
DB_PATH = os.path.join(TEST_DIR, "hippocampus.db")

@pytest.mark.asyncio
async def test_p10_auto_distill_trigger_audit():
    """Verify: not only is the Worker triggered, but Neocortex indeed produces valid summary content."""
    if os.path.exists(TEST_DIR): 
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)
    
    router = MemoryRouter(db_dir=TEST_DIR, distill_threshold=50)
    
    print("\n[MARATHON TRIGGER TEST] Pumping 50 messages...")
    for i in range(50):
        # Pump messages with semantics to produce a more meaningful summary
        await router.ingest({
            "context_id": "marathon_audit", 
            "messages": [{"role": "user", "content": f"Fact #{i}: The system component {i} is verified."}]
        })
    
    print("Pumping complete. Waiting 15s for LLM Distillation (NC_DIST)...")
    await asyncio.sleep(15.0)
    
    # Ultimate confirmation: penetration database audit
    print("\n[DATABASE PENETRATION AUDIT]")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT summary_text FROM neocortex_summaries WHERE context_id='marathon_audit'")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        pytest.fail("AUDIT FAIL: No summary record found in neocortex_summaries table.")
    
    summary_text = row[0]
    print(f"Captured Summary: {summary_text[:150]}...")
    
    # Assertion logic: non-empty, no error
    assert len(summary_text) > 10, "Summary text is too short."
    assert not summary_text.startswith("[Error]"), f"Summary contains distillation error: {summary_text}"
    
    print("AUDIT SUCCESS: Real knowledge found in Neocortex.")
