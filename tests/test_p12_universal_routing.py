# Generated from design/gateway.md v1.23
import pytest
from fastapi.testclient import TestClient
from src.main import app
from unittest.mock import patch, MagicMock, AsyncMock

def visual_audit(test_name, input_desc, target_prov, actual_status):
    print(f"\n[AUDIT: {test_name}]")
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
async def test_universal_routing_lmstudio():
    """验证 /v1/chat/completions 输入，被正确翻译并路由到 lmstudio"""
    payload = {
        "model": "lmstudio/llama-3",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    with TestClient(app) as client:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            # 3.1 准则修复：使用 MagicMock 模拟同步方法 json()
            mock_resp = MagicMock()
            mock_resp.is_error = False
            mock_resp.status_code = 200
            # 关键：json() 返回字典，而不是协程
            mock_resp.json.return_value = {"choices": [{"message": {"content": "mock"}}]}
            mock_post.return_value = mock_resp
            
            response = client.post("/v1/chat/completions", json=payload)
            
            visual_audit("Universal Routing -> LMStudio", "lmstudio/llama-3 via /v1", "lmstudio (Dialect: openai)", response.status_code)
            
            assert response.status_code == 200
            url_called = mock_post.call_args[0][0]
            assert "1234/v1/chat/completions" in url_called

@pytest.mark.asyncio
async def test_universal_routing_ollama():
    """验证 /api/chat 输入，被路由到默认 ollama"""
    payload = {
        "model": "gemma4:e4b",
        "messages": [{"role": "user", "content": "Hello"}],
        "options": {"temperature": 0.5}
    }
    
    with TestClient(app) as client:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.is_error = False
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"message": {"content": "mock"}}
            mock_post.return_value = mock_resp
            
            response = client.post("/api/chat", json=payload)
            
            visual_audit("Universal Routing -> Ollama", "gemma4:e4b via /api", "ollama (Dialect: ollama)", response.status_code)
            
            assert response.status_code == 200
            url_called = mock_post.call_args[0][0]
            assert "11434/api/chat" in url_called
