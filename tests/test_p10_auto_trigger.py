# Generated from design/memory_router.md v1.10
import pytest
import os
import shutil
import asyncio
from src.memory.router import MemoryRouter
from src.memory.storage import clear_chroma_clients

@pytest.mark.asyncio
async def test_p10_auto_distill_trigger_audit(tmp_path):
    """Verify: not only is the Worker triggered, but Neocortex indeed produces valid summary content."""
    clear_chroma_clients()
    test_dir = str(tmp_path)
    
    router = MemoryRouter(db_dir=test_dir, distill_threshold=50)
    
    print("\n[MARATHON TRIGGER TEST] Pumping 50 messages...")
    for i in range(50):
        # Pump messages with semantics to produce a more meaningful summary
        await router.ingest({
            "messages": [{"role": "user", "content": f"Fact #{i}: The system component {i} is verified."}]
        }, context_id="marathon_audit")
    
    print("Pumping complete. Waiting 15s for LLM Distillation (NC_DIST)...")
    await asyncio.sleep(15.0)
    
    # Ultimate confirmation: penetration database audit (Now ChromaDB)
    print("\n[DATABASE PENETRATION AUDIT]")
    res = router.neo.summary_col.get(ids=["marathon_audit"])
    
    if not res or not res["documents"]:
        pytest.fail("AUDIT FAIL: No summary record found in ChromaDB collection.")
    
    summary_text = res["documents"][0]
    print(f"Captured Summary: {summary_text[:150]}...")
    
    # Assertion logic: non-empty, no error
    assert len(summary_text) > 10, "Summary text is too short."
    assert not summary_text.startswith("[Error]"), f"Summary contains distillation error: {summary_text}"
    
    print("AUDIT SUCCESS: Real knowledge found in Neocortex.")
