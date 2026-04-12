# Generated from design/memory_router.md v1.10
import pytest
import os
import shutil
import asyncio
import time
import httpx
from src.memory.router import MemoryRouter
from src.memory.storage import clear_chroma_clients

async def is_ollama_ready():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
            return resp.status_code == 200
    except:
        return False

@pytest.mark.asyncio
async def test_p10_auto_distill_trigger_audit(tmp_path):
    """
    实测态度：验证异步提纯。
    无限轮询，直到 LLM 完成冷启动并生成摘要。
    """
    if not await is_ollama_ready():
        pytest.skip("Ollama is not running on 127.0.0.1:11434. Skipping real distillation test.")

    clear_chroma_clients()
    test_dir = str(tmp_path)
    
    # 显式使用较快的模型 qwen2.5:latest 
    router = MemoryRouter(db_dir=test_dir, distill_threshold=50, 
                          distill_model="qwen2.5:latest", enable_room_detection=False)
    
    # Phase 36: Synchronize with background initialization
    await router.wait_until_ready()
    
    threshold = router.distill_threshold
    session_id = "marathon_audit"
    print(f"\n[MARATHON TRIGGER TEST] Pumping {threshold} messages into session: {session_id}...")
    
    for i in range(threshold):
        await router.ingest({
            "messages": [{"role": "user", "content": f"Fact #{i}: The system component {i} is verified."}]
        }, context_id=session_id, sync_distill=True)
    
    # ── 关键变更：无限轮询 ──
    print("Ingestion complete. Waiting for Neocortex summary (NC_DIST) to appear...")
    
    start_time = time.time()
    summary_text = None
    
    while True:
        elapsed = int(time.time() - start_time)
        print(f"  > Polling... ({elapsed}s elapsed)")
        res = router.neo.summary_col.get(ids=[session_id])
        if res and res["documents"]:
            summary_text = res["documents"][0]
            if not summary_text.startswith("[Error]"):
                print(f"Success! Summary detected after {elapsed}s.")
                break
        
        # Safety break for absolute hung state (e.g. 10 mins) to prevent CI bill explosion
        if elapsed > 600:
            pytest.fail("AUDIT FAIL: No summary record found even after 10 minutes.")
            
        await asyncio.sleep(5.0) 
    
    print(f"\n[DATABASE PENETRATION AUDIT SUCCESS]")
    assert len(summary_text) > 10
    assert not summary_text.startswith("[Error]")
