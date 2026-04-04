# Generated from design/gateway.md v1.32
import pytest
from fastapi.testclient import TestClient
from src.main import app

def visual_audit(test_name, input_desc, expected_provider, actual_status):
    print(f"\n[REAL-WORLD AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_desc}")
    print("-" * 60)
    print(f"{'EXPECTED PROVIDER':<27} | {'ACTUAL STATUS'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{expected_provider:<27} | {actual_status}")
    print("-" * 60)
    print(f"VERDICT: {'PASS' if actual_status in [200, 501] else 'FAIL'}")
    print("=" * 60)

@pytest.mark.asyncio
async def test_lmstudio_real_routing():
    """验证 lmstudio/ 前缀通过网关真实转发到本地 1234 端口"""
    # 注意：确保您的 LM Studio 已经加载了模型
    payload = {
        "model": "lmstudio/any-model",
        "messages": [{"role": "user", "content": "Hello LM Studio, are you there?"}],
        "stream": False
    }
    
    with TestClient(app) as client:
        # 1. 直接请求网关
        response = client.post("/v1/chat/completions", json=payload)
        
        visual_audit("LM Studio Real Routing", "lmstudio/any-model", "LM Studio (Local:1234)", response.status_code)
        
        # 如果 LM Studio 在运行，应该返回 200 或由于模型未加载返回相应错误，
        # 但绝不应该是 404 (Ollama 回退) 或 501 (路由未命中)
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_openai_routing_security():
    """验证非法模型 (gpt-4) 在 OpenAI 入口下被正确拦截并返回 501"""
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello OpenAI"}]
    }
    
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=payload)
        
        visual_audit("OpenAI Routing Security", "gpt-4 (unauthorized)", "501 Block", response.status_code)
        
        # 2.2 准则修复：非法模型必须返回 501，严禁发往 Ollama 导致 404
        assert response.status_code == 501
