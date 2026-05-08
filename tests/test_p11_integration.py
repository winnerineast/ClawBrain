# Generated from design/memory_integration.md v1.5
import pytest
import json
import os
import shutil
import time
import httpx
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
    """Phase 11 Real environment integration audit: verify memory echo using active local model."""
    if os.path.exists(TEST_DB_DIR): shutil.rmtree(TEST_DB_DIR)
    os.makedirs(TEST_DB_DIR)
    os.environ["CLAWBRAIN_DB_DIR"] = TEST_DB_DIR
    
    # --- Discover what model is actually running to avoid 502 ---
    distill_url = os.getenv("CLAWBRAIN_DISTILL_URL", "http://localhost:11434")
    test_model = os.getenv("CLAWBRAIN_DISTILL_MODEL")
    
    if not test_model:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Probe based on port
                if "1234" in distill_url or "8080" in distill_url:
                    m_resp = await client.get(f"{distill_url}/v1/models")
                    if m_resp.status_code == 200:
                        data = m_resp.json().get("data", [])
                        if data: test_model = data[0]["id"]
                elif "11434" in distill_url:
                    m_resp = await client.get(f"{distill_url}/api/tags")
                    if m_resp.status_code == 200:
                        models = m_resp.json().get("models", [])
                        if models: test_model = models[0]["name"]
        except: pass

    # Last resort fallback
    if not test_model: test_model = "gemma4:e4b"

    with TestClient(app) as client:
        # Round 1: Plant secret
        payload1 = {
            "model": test_model,
            "messages": [{"role": "user", "content": "The secret code is APPLE-777"}],
            "stream": False
        }
        resp1 = client.post("/api/chat", json=payload1)
        if resp1.status_code != 200:
            pytest.skip(f"Live LLM returned {resp1.status_code} ({resp1.text}). Skipping E2E test.")
            
        # Ensure async ingestion and WM persistence are complete
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
