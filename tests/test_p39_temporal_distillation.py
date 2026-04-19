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
    router = MemoryRouter(db_dir=db_dir, distill_threshold=5, enable_room_detection=False)
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
    # Since it's async, we poll for the summary (using REAL time)
    print("\n[TEMPORAL TEST] Ingested 5 turns. Polling for summary...")
    
    start_poll = time.monotonic()
    safety_limit = 300 # 5 minutes for slow hardware
    summary = None
    while time.monotonic() - start_poll < safety_limit:
        summary = router.neo.get_summary(session_id)
        if summary and not summary.startswith("[Error]"):
            print(f"Success! Summary generated in {int(time.monotonic() - start_poll)}s")
            break
        
        if summary and summary.startswith("[Error]"):
            # Check if it's a transient connection error
            if "connection error" in summary.lower():
                pass # Continue polling
            else:
                pytest.fail(f"Distillation failed with critical error: {summary}")
                
        await asyncio.sleep(5)
    
    assert summary is not None, f"Distillation failed to produce a summary within {safety_limit}s"
    print(f"Resulting Summary:\n{summary}")
    
    # Verify that critical facts were preserved despite the "noise" and temporal spread
    # We look for keywords that should be in the distilled summary
    assert "Minecraft" in summary or "house" in summary
    assert "oak" in summary.lower() or "wood" in summary.lower()
    assert "cobblestone" in summary.lower()
    assert "blue bed" in summary.lower() or "bedroom" in summary.lower()
