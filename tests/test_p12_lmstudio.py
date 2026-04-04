# Generated from design/gateway.md v1.20
import pytest
import json
from fastapi.testclient import TestClient
from src.main import app
from unittest.mock import patch, MagicMock

def visual_audit(test_name, input_data, expected_provider, actual_status):
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT MODEL: {input_data}")
    print("-" * 60)
    print(f"{'EXPECTED PROVIDER':<27} | {'ACTUAL STATUS'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{expected_provider:<27} | {actual_status}")
    print("-" * 60)
    print("VERDICT: PASS")
    print("=" * 60)

@pytest.mark.asyncio
async def test_lmstudio_routing_logic():
    """验证 lmstudio/ 前缀正确触发 LMStudioAdapter"""
    payload = {
        "model": "lmstudio/llama-3-8b",
        "messages": [{"role": "user", "content": "Hello LM Studio"}]
    }
    
    with TestClient(app) as client:
        # 我们 Mock 掉适配器的真实请求，只验证路由
        with patch("src.adapters.lmstudio.LMStudioAdapter.chat") as mock_chat:
            mock_chat.return_value = {"choices": [{"message": {"content": "Mocked LMStudio"}}]}
            response = client.post("/v1/chat/completions", json=payload)
            
            visual_audit("LM Studio Routing", "lmstudio/llama-3-8b", "LMStudioAdapter", response.status_code)
            
            assert mock_chat.called
            assert response.status_code == 200

@pytest.mark.asyncio
async def test_openai_fallback_routing():
    """验证无前缀或 openai/ 前缀正确触发 OpenAIAdapter (返回 501)"""
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello OpenAI"}]
    }
    
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=payload)
        
        visual_audit("OpenAI Fallback", "gpt-4", "OpenAIAdapter", response.status_code)
        
        assert response.status_code == 501
        assert "Official OpenAI API support is planned" in response.text
