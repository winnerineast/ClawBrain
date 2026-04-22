import pytest
import os
import asyncio
import httpx
import time
from src.memory.router import MemoryRouter
from src.memory.storage import clear_chroma_clients

async def is_ollama_ready():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags", timeout=1.0)
            return resp.status_code == 200
    except:
        return False

@pytest.mark.asyncio
async def test_p34_room_auto_segmentation(tmp_path):
    """Real-world Audit: Verify LLM's automatic room segmentation in a live environment."""
    if not await is_ollama_ready():
        pytest.skip("Ollama not running. Skipping real room test.")

    clear_chroma_clients()
    test_dir = str(tmp_path)
    
    # Explicitly configure real model
    router = MemoryRouter(db_dir=test_dir, distill_model="qwen2.5:latest")
    await router.wait_until_ready()
    session_id = "segment-test"
    
    # Turn 1: Database topic
    print("\n[ROOM TEST] Turn 1: Database optimization...")
    await router.ingest({"messages": [{"role": "user", "content": "How to create an index in Postgres?"}]}, session_id=session_id)
    
    # --- Critical Change: Poll until Room changes ---
    print("Waiting for LLM to detect topic shift (Room change)...")
    start_time = time.time()
    room_detected = False
    
    while time.time() - start_time < 60: # 60s is enough for one detection
        if router._get_current_room(session_id) != "general":
            print(f"Success! Internal Room state updated: {router._get_current_room(session_id)}")
            room_detected = True
            break
        await asyncio.sleep(2.0)
        
    assert room_detected, "Real LLM failed to update internal room state within 60s."

    # Turn 2: Should now be saved in the new room
    print("[ROOM TEST] Turn 2: Saving in detected room...")
    await router.ingest({"messages": [{"role": "user", "content": "Another DB query"}]}, session_id=session_id)
    
    recent = router.hippo.get_recent_traces(limit=10, session_id=session_id)
    rooms = [t["room_id"] for t in recent]
    print(f"[ROOM AUDIT] Captured rooms in Hippo: {rooms}")
    
    assert any(r != "general" for r in rooms), "No traces found in specific rooms in Hippo."

@pytest.mark.asyncio
async def test_p34_room_prioritized_search(tmp_path):
    """Verify that search favors content from the current room (Unit logic test)"""
    clear_chroma_clients()
    test_dir = str(tmp_path)
    router = MemoryRouter(db_dir=test_dir)
    await router.wait_until_ready()
    session_id = "search-test"
    
    # Manually plant traces in different rooms
    router.hippo.save_trace("t1", {"stimulus": {"messages": [{"role": "user", "content": "Backend: FastAPI is for Python"}]}}, 
                            search_text="backend info", session_id=session_id, room_id="backend")
    router.hippo.save_trace("t2", {"stimulus": {"messages": [{"role": "user", "content": "Frontend: Vue is for JS"}]}}, 
                            search_text="frontend info", session_id=session_id, room_id="frontend")
    
    # Mock Cognitive Judge for unit test
    async def mock_verify(*args, **kwargs): return True
    router.neo.verify_relevance = mock_verify
    
    # Case A: Current room is 'backend'
    router._current_rooms[session_id] = "backend"
    context_a = await router.get_combined_context(session_id, "backend python")
    assert "FastAPI" in context_a
    
    # Case B: Current room is 'frontend'
    router._current_rooms[session_id] = "frontend"
    context_b = await router.get_combined_context(session_id, "frontend vue")
    assert "Vue" in context_b
