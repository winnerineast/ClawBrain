# Generated from design/gateway.md v1.36
import pytest
import httpx
import os
import subprocess
import time
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app
from src.memory.storage import clear_chroma_clients

def get_running_ollama_models():
    try:
        result = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")[1:]
        return [line.split()[0] for line in lines if line]
    except:
        return []

@pytest.fixture(scope="module")
def gpu_resource_manager():
    """
    Setup: Save & Stop Ollama models to free VRAM for LM Studio.
    Teardown: (Optional)
    """
    print("\n[GPU_RESOURCES] Releasing VRAM: Stopping Ollama models...")
    original_models = get_running_ollama_models()
    for m in original_models:
        subprocess.run(["ollama", "stop", m])
    
    yield original_models
    print("[GPU_RESOURCES] VRAM released.")

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
async def test_lmstudio_real_routing(gpu_resource_manager, tmp_path):
    """验证 lmstudio/ 前缀通过网关真实转发到用户运行的 LM Studio 实例"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)
    os.environ["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"
    
    # --- 探测 LM Studio 已加载的模型 ---
    url = "http://127.0.0.1:1234/v1/models"
    real_model_id = None
    print(f"\n[SCOUT] Probing LM Studio for active models at {url}...")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            m_resp = await client.get(url)
            if m_resp.status_code == 200:
                models = m_resp.json().get("data", [])
                if models:
                    real_model_id = models[0]["id"]
                    print(f"[SCOUT] LM Studio found! Active Model: {real_model_id}")
    except Exception as e:
        print(f"[SCOUT] LM Studio probe failed: {e}")

    if not real_model_id:
        pytest.skip("No active model found in LM Studio. Skipping real-routing test.")

    payload = {
        "model": f"lmstudio/{real_model_id}",
        "messages": [{"role": "user", "content": "Hello LM Studio, identify yourself."}],
        "stream": False
    }
    
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=payload)
        visual_audit("LM Studio Real Routing", f"lmstudio/{real_model_id}", "LM Studio (User Instance)", response.status_code)
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_openai_routing_security():
    """验证非法模型 (gpt-4) 在 OpenAI 入口下被正确拦截"""
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello OpenAI"}]
    }
    
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=payload)
        visual_audit("OpenAI Routing Security", "gpt-4 (unauthorized)", "501 Block", response.status_code)
        assert response.status_code == 501
