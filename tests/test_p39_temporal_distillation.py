import pytest
import os
import asyncio
import time
from unittest.mock import patch
from src.memory.router import MemoryRouter
from src.memory.storage import clear_chroma_clients

@pytest.mark.asyncio
async def test_temporal_distillation_logic(tmp_path):
    """
    Issue #20: Verify distillation with realistic temporal gaps and noisy data.
    """
    clear_chroma_clients()
    db_dir = str(tmp_path)
    
    # Use a small threshold for testing
    router = MemoryRouter(
        db_dir=db_dir, 
        distill_threshold=5, 
        enable_room_detection=False,
        enable_auto_scan=False,
        enable_cognitive_plane=True
    )
    await router.wait_until_ready()
    
    session_id = "temporal-audit-session"
    
    # 1. Ingest noisy conversation history with mocked temporal gaps
    # We mock time.time() to simulate turns happening over hours
    base_time = time.time() - 3600 * 5 # 5 hours ago
    
    noisy_turns = [
        "User: Hello, I want to build a house in Minecraft.",
        "Assistant: Sure! What materials do you like?",
        "User: I like oak wood and cobblestone.",
        "Assistant: Great choices. How many rooms?",
        "User: Three rooms, and use a blue bed in the bedroom."
    ]
    
    for i, turn in enumerate(noisy_turns):
        with patch('time.time') as mock_time:
            mock_time.return_value = base_time + (i * 600) # One turn every 10 mins
            await router.ingest({"messages": [{"role": "user", "content": turn}]}, session_id=session_id)
            
    # The 5th turn should have triggered distillation (threshold=5)
    # Force the heartbeat to run immediately
    router.nudge()
    print("\n[TEMPORAL TEST] Ingested 5 turns. Polling for thoughts...")
    
    start_poll = time.monotonic()
    safety_limit = 120 # 2 minutes
    thoughts = []
    while time.monotonic() - start_poll < safety_limit:
        thoughts = router.hippo.search_thoughts("", session_id=session_id)
        if thoughts:
            print(f"Success! {len(thoughts)} thoughts generated in {int(time.monotonic() - start_poll)}s")
            break
        await asyncio.sleep(2)
    
    assert len(thoughts) > 0, f"Distillation failed to produce thoughts within {safety_limit}s"
    
    combined_thoughts = " ".join([t["thought"] for t in thoughts]).lower()
    print(f"Resulting Thoughts:\n{combined_thoughts}")
    
    # Verify that critical facts were preserved
    assert "minecraft" in combined_thoughts or "house" in combined_thoughts
    assert "oak" in combined_thoughts or "wood" in combined_thoughts
    assert "cobblestone" in combined_thoughts
    assert "blue bed" in combined_thoughts or "bedroom" in combined_thoughts
    await router.aclose()
