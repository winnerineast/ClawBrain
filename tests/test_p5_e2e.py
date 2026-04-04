# Generated from design/gateway.md v1.18
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app

def visual_audit(test_name, input_summary, expected, actual):
    match = "YES" if str(expected) in str(actual) or expected == actual else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_summary}")
    print("-" * 60)
    print(f"EXPECTED: {expected}")
    print(f"ACTUAL:   {str(actual)[:100]}...")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

@pytest.mark.asyncio
async def test_e2e_ollama_chat_lifespan():
    payload = {"model": "gemma4:e4b", "messages": [{"role": "user", "content": "1+1=?"}], "stream": False}
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        visual_audit("E2E Chat", "1+1=?", "2", response.text)
        assert response.status_code == 200
        assert "2" in response.text

@pytest.mark.asyncio
async def test_e2e_qualification_interception():
    payload = {
        "model": "qwen2.5:latest",
        "messages": [{"role": "user", "content": "test"}],
        "tools": [{"type": "function", "function": {"name": "test"}}]
    }
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        visual_audit("E2E Qualification", "Qwen + Tools", 422, response.status_code)
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_e2e_multi_round_marathon():
    data_path = Path("tests/data/p5_multi_round.json")
    thread = json.loads(data_path.read_text())["multi_round_thread"]
    thread.append({"role": "user", "content": "Round 21: Summary?"})
    
    payload = {"model": "gemma4:e4b", "messages": thread, "stream": False}
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        visual_audit("E2E Marathon", "21 Rounds technical thread", "Status 200", response.status_code)
        assert response.status_code == 200
        assert len(response.json()["message"]["content"]) > 10
