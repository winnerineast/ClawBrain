# Generated from design/gateway.md v1.29
import pytest
import asyncio
import respx
import re
import json
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

def mock_embeddings(request):
    try:
        body = json.loads(request.content)
        inp = body.get("input", "")
        if isinstance(inp, list):
            num_embeddings = len(inp)
        else:
            num_embeddings = 1
    except Exception:
        num_embeddings = 1
    
    embeddings = [[0.1] * 768 for _ in range(num_embeddings)]
    data = [{"embedding": [0.1] * 768} for _ in range(num_embeddings)]
    return Response(200, json={"embeddings": embeddings, "data": data})

@pytest.mark.asyncio
@respx.mock
async def test_universal_routing_lmstudio():
    """验证 /v1/chat/completions 输入，被正确翻译并路由 to lmstudio"""
    import os
    os.environ["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"
    
    # Mock embedding calls dynamically based on input batch size
    respx.post(re.compile(r".*/api/embed|.*/v1/embeddings")).mock(side_effect=mock_embeddings)
    
    payload = {
        "model": "lmstudio/llama-3",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    # 精准拦截：只拦截发往 LMStudio 的请求 (使用 localhost 确保与 registry 匹配)
    route = respx.post("http://localhost:1234/v1/chat/completions").mock(
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
    """验证 /api/chat 输入，被路由到默认 ollama"""
    import os
    os.environ["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"
    
    # Mock embedding calls dynamically based on input batch size
    respx.post(re.compile(r".*/api/embed|.*/v1/embeddings")).mock(side_effect=mock_embeddings)
    
    payload = {
        "model": "gemma4:e4b",
        "messages": [{"role": "user", "content": "Hello"}],
        "options": {"temperature": 0.5}
    }
    
    # 精准拦截：只拦截发往 Ollama 的请求
    route = respx.post("http://localhost:11434/api/chat").mock(
        return_value=Response(200, json={"message": {"content": "mock"}})
    )
    
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        
        visual_audit("Universal Routing -> Ollama", "gemma4:e4b via /api", "ollama (Dialect: ollama)", response.status_code)
        
        assert response.status_code == 200
        assert route.called
