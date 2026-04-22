# Generated from design/memory_router.md v1.10 / v0.2.1
import pytest
import os
import shutil
import asyncio
import time
import httpx
import random
from src.memory.router import MemoryRouter
from src.memory.storage import clear_chroma_clients

async def is_ollama_ready():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            return resp.status_code == 200
    except:
        return False

@pytest.mark.asyncio
async def test_p10_auto_distill_trigger_audit(tmp_path):
    """
    v0.2.1: Real-world Stress Test (LLM Optimized).
    Pumping 15 turns of varied development dialogue.
    """
    if not await is_ollama_ready():
        pytest.skip("Ollama is not running. Skipping stress test.")

    clear_chroma_clients()
    test_dir = str(tmp_path)

    # Threshold set to 10 to ensure we trigger dirty state with 15 messages
    router = MemoryRouter(db_dir=test_dir, distill_threshold=10,
                          distill_model="qwen2.5:latest", enable_room_detection=False)
    await router.wait_until_ready()

    session_id = "marathon_real_world"
    
    # ── HIGH-FIDELITY TEST DATASET ──
    topics = [
        "Backend: We chose FastAPI with Python 3.12.",
        "Database: Production DB moved to 10.0.5.20 (Postgres 15).",
        "Frontend: User prefers Tailwind CSS over Bootstrap.",
        "Infrastructure: Kubernetes cluster is running on version 1.28.",
        "Team: Alice is the lead architect.",
    ]
    
    print(f"\n[MARATHON TEST] Pumping 15 turns of dialogue...")
    
    for i in range(15):
        content = topics[i % len(topics)]
        await router.ingest({
            "messages": [{"role": "user", "content": f"Turn {i}: {content}"}]
        }, session_id=session_id)

    # ── THE BREATHE TRIGGER ──
    print("Ingestion complete. Triggering brain processing cycle...")
    # Triggering breathe manually
    await router.breathe()
    
    # v0.2.1: Give the LLM some time to finish the distill call which was triggered by breathe
    # Even though breathe awaits _auto_distill_worker, let's be safe.
    await asyncio.sleep(2.0)
    
    # ── VERIFICATION ──
    # Check for Distilled Thoughts (Semantic insights)
    res = router.hippo.thoughts_col.get(where={"session_id": session_id})
    
    print(f"\n[STRESS TEST AUDIT]")
    print("-" * 50)
    print(f"Total Thoughts Found: {len(res['documents'])}")
    for i, doc in enumerate(res['documents']):
        print(f"Thought {i+1}: {doc[:100]}...")
        
    assert len(res['documents']) > 0, "Brain failed to generate thoughts. Check LLM logs."
    
    await router.aclose()
