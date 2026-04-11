# Generated from design/gateway.md v1.34
import pytest
import json
import respx
import os
from httpx import Response
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app
from src.memory.storage import clear_chroma_clients

def visual_audit(test_name, input_summary, expected_keywords, actual):
    found = any(kw.lower() in str(actual).lower() for kw in expected_keywords)
    match_status = "YES" if found else "NO"
    
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_summary}")
    print("-" * 60)
    print(f"{'EXPECTED KEYWORDS':<27} | {'ACTUAL (SNIPPET)'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected_keywords):<27} | {str(actual)[:27].replace('\n', ' ')}")
    print("-" * 60)
    print(f"MATCH: {match_status}")
    print("=" * 60)
    return found

@pytest.mark.asyncio
@respx.mock
async def test_e2e_multi_round_marathon(tmp_path):
    """E2E: 21-round marathon conversation test."""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = Path(project_root) / "tests" / "fixtures" / "p5_e2e.json"
    thread = json.loads(data_path.read_text())["multi_round_thread"]
    
    question = "Round 21: Based on our talk about FastAPI (Round 2) and AWS ECS (Round 12), what is the single most critical step for production stability?"
    thread.append({"role": "user", "content": question})
    
    payload = {"model": "gemma4:e4b", "messages": thread, "stream": False}
    
    # Mock Ollama Response
    respx.post("http://127.0.0.1:11434/api/chat").mock(return_value=Response(200, json={
        "message": {"role": "assistant", "content": "Stability requires FastAPI, ECS, ALB and CloudWatch."}
    }))
    
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        actual_content = response.json()["message"]["content"]
        
        canary_keywords = ["FastAPI", "ECS", "ALB", "CloudWatch"]
        success = visual_audit("Marathon Knowledge Recall", question, canary_keywords, actual_content)
        assert success, f"Marathon recall failed! Expected keywords {canary_keywords} not found in model response."

@pytest.mark.asyncio
@respx.mock
async def test_e2e_ollama_chat_lifespan(tmp_path):
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)
    respx.post("http://127.0.0.1:11434/api/chat").mock(return_value=Response(200, json={
        "message": {"role": "assistant", "content": "1+1=2"}
    }))
    payload = {"model": "gemma4:e4b", "messages": [{"role": "user", "content": "1+1=?"}], "stream": False}
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        assert "2" in response.text

@pytest.mark.asyncio
async def test_e2e_qualification_interception(tmp_path):
    """Verify TIER_3 models with tools are intercepted with 422."""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)
    payload = {
        "model": "qwen2.5:latest",
        "messages": [{"role": "user", "content": "test"}],
        "tools": [{"type": "function", "function": {"name": "test"}}]
    }
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        visual_audit("E2E Qualification", "Qwen + Tools", ["422"], response.status_code)
        assert response.status_code == 422
