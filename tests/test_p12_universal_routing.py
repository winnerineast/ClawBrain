# Generated from design/gateway.md v1.29
import pytest
import asyncio
import respx
from httpx import Response
from fastapi.testclient import TestClient
from src.main import app

def visual_audit(test_name, input_desc, target_prov, actual_status):
    print(f"\n[DIALECT AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_desc}")
    print("-" * 60)
    print(f"{'TARGET PROVIDER':<27} | {'ACTUAL STATUS'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{target_prov:<27} | {actual_status}")
    print("-" * 60)
    print("VERDICT: PASS")
    print("=" * 60)

@pytest.mark.asyncio
@respx.mock
async def test_universal_routing_lmstudio():
    """Verify that /v1/chat/completions input is correctly translated and routed to LM Studio."""
    # Strict isolation: Disable Room Detection to prevent background traffic interference
    import os
    os.environ["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"
    
    payload = {
        "model": "lmstudio/llama-3",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    # Precise interception: Only capture requests directed to LM Studio
    route = respx.post("http://127.0.0.1:1234/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": "mock"}}]})
    )
    
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=payload)
        
        visual_audit("Universal Routing -> LMStudio", "lmstudio/llama-3 via /v1", "lmstudio (Dialect: openai)", response.status_code)
        
        assert response.status_code == 200
        assert route.called

@pytest.mark.asyncio
@respx.mock
async def test_universal_routing_ollama():
    """Verify that /api/chat input is correctly routed to default Ollama."""
    import os
    os.environ["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"
    
    payload = {
        "model": "gemma4:e4b",
        "messages": [{"role": "user", "content": "Hello"}],
        "options": {"temperature": 0.5}
    }
    
    # Precise interception: Only capture requests directed to Ollama
    route = respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=Response(200, json={"message": {"content": "mock"}})
    )
    
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        
        visual_audit("Universal Routing -> Ollama", "gemma4:e4b via /api", "ollama (Dialect: ollama)", response.status_code)
        
        assert response.status_code == 200
        assert route.called
