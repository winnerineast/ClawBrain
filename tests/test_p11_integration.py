# Generated from design/memory_integration.md v1.4
import pytest
import json
import os
import shutil
import time
import respx
from httpx import Response
from fastapi.testclient import TestClient
from src.main import app

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DB_DIR = os.path.join(PROJECT_ROOT, "tests/data/p11_real_tmp")

def visual_audit_memory(test_name, round_num, input_data, expected_recall, actual_payload):
    print(f"\n[REAL E2E AUDIT: {test_name} - Round {round_num}]")
    print("=" * 80)
    print(f"INPUT: {input_data}")
    print("-" * 80)
    print(f"{'EXPECTED RECALL':<38} | {'ACTUAL ENHANCEMENT'}")
    
    actual_snippet = str(actual_payload)[:100].replace('\n', ' ')
    print(f"{expected_recall:<38} | {actual_snippet}")
    print("-" * 80)
    print(f"MEMORY ECHO MATCH: {'YES' if expected_recall.lower() in str(actual_payload).lower() else 'NO'}")
    print("=" * 80)

@pytest.mark.asyncio
async def test_p11_full_chain_memory_echo_real():
    """Phase 11 Real environment integration audit: verify memory echo using real local services."""
    if os.path.exists(TEST_DB_DIR): shutil.rmtree(TEST_DB_DIR)
    os.makedirs(TEST_DB_DIR)
    
    # Force isolated DB path via environment
    os.environ["CLAWBRAIN_DB_DIR"] = TEST_DB_DIR
    
    # NO MOCKS: Communication occurs with real local services (Ollama/LM Studio)
    # The system will use LLMFactory.from_env() internally via MemoryRouter

    with TestClient(app) as client:
        # Round 1: Plant secret
        # Use gemma4:e4b which was verified as available
        payload1 = {
            "model": "gemma4:e4b",
            "messages": [{"role": "user", "content": "The secret code is APPLE-777"}]
        }
        resp1 = client.post("/api/chat", json=payload1)
        assert resp1.status_code == 200
        
        # Ensure async ingestion and WM persistence are complete
        # Live LLMs may take a moment to respond; wait for the heartbeat/solidification
        time.sleep(3.0)
        
        # Round 2: Verify recall
        memory = client.app.state.memory_router
        enhanced_context = await memory.get_combined_context("default", "secret code")
        
        visual_audit_memory(
            "Real Environment Echo",
            2,
            "Recall secret code",
            "APPLE-777",
            enhanced_context
        )
        
        assert "APPLE-777" in enhanced_context
        assert "WORKING MEMORY" in enhanced_context or "HIPPOCAMPUS" in enhanced_context
