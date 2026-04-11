import pytest
import os
import asyncio
import respx
from httpx import Response
from src.memory.router import MemoryRouter
from src.memory.storage import clear_chroma_clients

@pytest.mark.asyncio
@respx.mock
async def test_p34_room_auto_segmentation(tmp_path):
    """Verify that conversation correctly segments into distinct rooms based on topics."""
    clear_chroma_clients()
    test_dir = str(tmp_path)
    
    # Mock LLM for Room Detection
    # 1. First turn: Database topic -> 'database' room
    # 2. Second turn: Frontend topic -> 'ui' room
    respx.post("http://127.0.0.1:11434/api/generate").mock(side_effect=[
        Response(200, json={"response": "database"}),
        Response(200, json={"response": "ui"})
    ])
    
    router = MemoryRouter(db_dir=test_dir)
    session_id = "segment-test"
    
    # Turn 1: Database
    await router.ingest({"messages": [{"role": "user", "content": "How to optimize Postgres?"}]}, context_id=session_id)
    # Wait for async room update
    await asyncio.sleep(0.5)
    
    # Turn 2: Frontend (Should trigger room shift)
    await router.ingest({"messages": [{"role": "user", "content": "React button styling"}]}, context_id=session_id)
    await asyncio.sleep(0.5)
    
    # Verify rooms in Hippocampus
    # We expect 2 traces in different rooms
    recent = router.hippo.get_recent_traces(limit=10, context_id=session_id)
    
    # Trace 1 was saved BEFORE detection (uses default 'general' or previous)
    # Trace 2 was saved AFTER first detection (uses 'database')
    # Actually, ingest uses CURRENT room then triggers NEXT. 
    # Let's check the metadata of saved traces.
    
    rooms = [t["room_id"] for t in recent]
    print(f"\n[ROOM AUDIT] Captured rooms: {rooms}")
    
    assert "database" in rooms or "ui" in rooms
    assert len(set(rooms)) >= 2, "Should have at least two distinct rooms (general + detected)"

@pytest.mark.asyncio
@respx.mock
async def test_p34_room_prioritized_search(tmp_path):
    """Verify that search favors content from the current room."""
    clear_chroma_clients()
    test_dir = str(tmp_path)
    router = MemoryRouter(db_dir=test_dir)
    session_id = "search-test"
    
    # Manually plant traces in different rooms
    # Room: 'backend'
    router.hippo.save_trace("t1", {"stimulus": {"content": "FastAPI is for Python"}}, 
                            search_text="backend info", context_id=session_id, room_id="backend")
    # Room: 'frontend'
    router.hippo.save_trace("t2", {"stimulus": {"content": "Vue is for JS"}}, 
                            search_text="frontend info", context_id=session_id, room_id="frontend")
    
    # Case A: Current room is 'backend'
    router._current_rooms[session_id] = "backend"
    context_a = await router.get_combined_context(session_id, "framework info")
    print(f"\n[SEARCH AUDIT] Context (Room=backend): {context_a}")
    assert "FastAPI" in context_a
    
    # Case B: Current room is 'frontend'
    router._current_rooms[session_id] = "frontend"
    context_b = await router.get_combined_context(session_id, "framework info")
    print(f"\n[SEARCH AUDIT] Context (Room=frontend): {context_b}")
    assert "Vue" in context_b
    
    # Verification of Fallback: 
    # If we search for something in the OTHER room that is highly specific, it should still find it.
    # Note: Our search priority is Phase 1 (Room) -> Phase 2 (Global).
    res = await router.get_combined_context(session_id, "python")
    assert "FastAPI" in res
