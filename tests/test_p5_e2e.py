# Generated from design/gateway.md v1.16
import pytest
import json
from fastapi.testclient import TestClient
from src.main import app

def audit_log(test_name, input_payload, expected, actual):
    print(f"\n[AUDIT START: {test_name}]")
    print(f"Input:    {repr(input_payload)}")
    print(f"Expected: {repr(expected)}")
    print(f"Actual:   {repr(actual)}")
    print("[AUDIT END]")

@pytest.mark.asyncio
async def test_e2e_ollama_chat_lifespan():
    """E2E: 验证对话全链路并确保触发 Lifespan 初始化"""
    payload = {
        "model": "gemma4:e4b",
        "messages": [{"role": "user", "content": "1+1=?"}],
        "stream": False
    }
    
    # 遵循 3.1 准则：必须使用 with 语法触发生命周期
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        
        audit_log("E2E Non-Stream Lifespan Check", payload, "Status 200", response.status_code)
        assert response.status_code == 200
        assert "2" in response.text

@pytest.mark.asyncio
async def test_e2e_qualification_interception():
    """E2E: 验证准入拦截逻辑"""
    # qwen2.5:latest (4.7B) 应被 TIER 3 判定拦截
    payload = {
        "model": "qwen2.5:latest",
        "messages": [{"role": "user", "content": "test"}],
        "tools": [{"type": "function", "function": {"name": "test"}}]
    }
    
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        
        audit_log("E2E Qualification Interception", payload, 422, response.status_code)
        assert response.status_code == 422
