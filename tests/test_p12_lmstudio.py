# Generated from design/gateway.md v1.36
import pytest
import httpx
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
    """验证 lmstudio/ 前缀通过网关真实转发，并自适应探测本地加载的模型名 (Fixed Bug 10)"""
    LMSTUDIO_V1_MODELS = "http://127.0.0.1:1234/v1/models"
    
    # 3.2 准则修正：自适应探测本地模型环境
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            m_resp = await client.get(LMSTUDIO_V1_MODELS)
            models = m_resp.json().get("data", [])
            if not models:
                pytest.skip("LM Studio is running but no models are loaded.")
            real_model_id = models[0]["id"]
            print(f"DEBUG: Detected loaded model in LM Studio: {real_model_id}")
    except Exception:
        pytest.skip("LM Studio is not reachable at 1234. Skipping real-world test.")

    payload = {
        "model": f"lmstudio/{real_model_id}",
        "messages": [{"role": "user", "content": "Hello LM Studio, identity yourself."}],
        "stream": False
    }
    
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=payload)
        
        # 诊断：打印真实的错误 Body，拒绝猜测
        if response.status_code != 200:
            print(f"\n[DIAGNOSTIC ERROR BODY]: {response.text}")
            
        visual_audit("LM Studio Adaptive Routing", f"lmstudio/{real_model_id}", "LM Studio (Local:1234)", response.status_code)
        
        # 此时后端必须返回 200，因为模型名已完全对齐
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
        assert response.status_code == 501
