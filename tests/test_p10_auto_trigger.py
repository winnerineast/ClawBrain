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
    """实测态度：检查本地 Ollama 服务是否可用"""
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
    不再 Mock，而是真实等待 Neocortex 在后台完成任务。
    """
    if not await is_ollama_ready():
        pytest.skip("Ollama is not running on 127.0.0.1:11434. Skipping real distillation test.")

    clear_chroma_clients()
    test_dir = str(tmp_path)
    
    # 显式关闭 Room Detection 以减少干扰，专注测试 Distillation
    router = MemoryRouter(db_dir=test_dir, distill_threshold=50, enable_room_detection=False)
    
    # 实测态度：不再硬编码 50 或 49，而是直接根据 router 的实际配置运行
    threshold = router.distill_threshold
    session_id = "marathon_audit"
    print(f"\n[MARATHON TRIGGER TEST] Pumping {threshold} messages into session: {session_id}...")
    
    for i in range(threshold):
        # 声明式同步：如果本回合触发了提纯，则等待其完成。
        # 这样测试逻辑就不需要关心具体的触发索引。
        await router.ingest({
            "messages": [{"role": "user", "content": f"Fact #{i}: The system component {i} is verified."}]
        }, context_id=session_id, sync_distill=True)
    
    # ── 关键变更：智能轮询（作为双重保障） ──
    print("Ingestion complete. Verifying summary presence...")
    
    max_wait = 60 # 极限等待 60 秒
    start_time = time.time()
    summary_text = None
    
    while time.time() - start_time < max_wait:
        res = router.neo.summary_col.get(ids=[session_id])
        if res and res["documents"]:
            summary_text = res["documents"][0]
            if not summary_text.startswith("[Error]"):
                print(f"Success! Summary detected after {int(time.time() - start_time)}s.")
                break
        await asyncio.sleep(2.0) # 每 2 秒检查一次
    
    if not summary_text:
        pytest.fail(f"AUDIT FAIL: No summary record found in ChromaDB after {max_wait}s timeout.")
    
    print(f"\n[DATABASE PENETRATION AUDIT SUCCESS]")
    print(f"Captured Summary: {summary_text[:150]}...")
    
    # 断言逻辑
    assert len(summary_text) > 10, "Summary text is too short."
    assert not summary_text.startswith("[Error]"), f"Summary contains error: {summary_text}"
