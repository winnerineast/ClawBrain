import pytest
import asyncio
import os
from src.memory.router import MemoryRouter, clear_chroma_clients

@pytest.mark.asyncio
async def test_p51_accelerated_breathing_lifecycle(tmp_path):
    """
    v0.2.1: Real-system accelerated test.
    We ingest data and then 'nudge' the brain to process it immediately,
    bypassing the 30s heartbeat but using 100% of the real logic.
    """
    clear_chroma_clients()
    test_dir = str(tmp_path)
    # Set a long heartbeat to prove that our nudge is what triggers the processing
    router = MemoryRouter(db_dir=test_dir, heartbeat_interval=3600, distill_threshold=1)
    await router.wait_until_ready()
    
    session_id = "accelerated-brain"
    
    # 1. Ingest a fact (this queues an entity extraction and marks session as dirty)
    # Use a content that triggers our extractor (mocked or real)
    payload = {
        "messages": [{"role": "user", "content": "Our project 'Claw' uses Python 3.12 and is hosted at 10.0.0.5."}]
    }
    await router.ingest(payload, session_id=session_id)
    
    # Verify: No thoughts yet (brain hasn't breathed)
    thoughts_before = router.hippo.search_thoughts("Python", session_id)
    assert len(thoughts_before) == 0
    
    # 2. FORCE BREATHE (The Nudge)
    # We mock the LLM returns for deterministic testing if no real backend is present,
    # but the logic flow (queue -> heartbeat -> extraction -> storage) is 100% real.
    
    # Mock EntityExtractor for this test to ensure it returns what we want
    async def mock_extract(text):
        return [{"entity": "Claw", "key": "version", "value": "3.12"}]
    router.entity_extractor.extract_entities = mock_extract
    
    # Mock Neocortex to produce a Thought
    async def mock_distill(sid, traces):
        router.hippo.upsert_thought(sid, "Project Claw is Python-based.", [t.get("trace_id") for t in traces if t.get("trace_id")])
        return "Done"
    router.neo.distill = mock_distill
    
    # Trigger the real breathe logic
    await router.breathe()
    
    # 3. Verify Results
    # The brain should have processed the queue
    entities = router.hippo.get_facts_for_entities(session_id, ["Claw"])
    assert len(entities) > 0
    assert entities[0]["value"] == "3.12"
    
    thoughts_after = router.hippo.search_thoughts("Python", session_id)
    assert len(thoughts_after) > 0
    assert "Claw" in thoughts_after[0]["thought"]
    
    await router.aclose()

@pytest.mark.asyncio
async def test_p51_nudge_signal_trigger(tmp_path):
    """Verify that nudge() actually wakes up the heartbeat loop."""
    clear_chroma_clients()
    # Interval = 1 hour
    router = MemoryRouter(db_dir=str(tmp_path), heartbeat_interval=3600)
    await router.wait_until_ready()
    
    # Spy on the breathe method
    original_breathe = router.breathe
    call_count = 0
    async def spy_breathe():
        nonlocal call_count
        call_count += 1
        await original_breathe()
    
    router.breathe = spy_breathe
    
    # Nudge the brain
    await router.nudge()
    
    # Give it a moment to wake up and execute
    await asyncio.sleep(0.1)
    
    assert call_count == 1
    await router.aclose()
