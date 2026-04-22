# Generated from design/gateway.md v1.36
import pytest
import httpx
import os
import shutil
import subprocess
import time
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app
from src.memory.storage import clear_chroma_clients, get_running_ollama_models
from src.gateway.detector import ProtocolDetector
from src.gateway.translator import DialectTranslator
from src.scout import ModelScout, ModelTier

def get_lms_bin():
    """v0.2.1: Dynamic binary lookup for portability (Ubuntu/MacOS)"""
    # 1. Environment Override
    env_bin = os.getenv("CLAWBRAIN_LMS_BIN")
    if env_bin: return env_bin
    
    # 2. Path Lookup
    path_bin = shutil.which("lms")
    if path_bin: return path_bin
    
    # 3. Common OS Defaults
    # Linux (Ubuntu)
    linux_path = os.path.expanduser("~/.lmstudio/bin/lms")
    if os.path.exists(linux_path): return linux_path
    
    # MacOS
    macos_path = "/Applications/LM Studio.app/Contents/MacOS/lms"
    if os.path.exists(macos_path): return macos_path
    
    return "lms" # Final fallback

@pytest.fixture(scope="module")
def gpu_resource_manager():
    """
    Setup: Save & Stop Ollama models, Load LM Studio.
    Teardown: Unload LM Studio.
    """
    lms_bin = get_lms_bin()
    print(f"\n[GPU_RESOURCES] Detecting active Ollama models...")
    original_models = get_running_ollama_models()

    if original_models:
        print(f"[GPU_RESOURCES] Releasing VRAM: Stopping {original_models}")
        for m in original_models:
            subprocess.run(["ollama", "stop", m])

    # Load LM Studio model
    print(f"[GPU_RESOURCES] Loading LM Studio model (qwen/qwen3.5-2b) via {lms_bin}...")
    subprocess.run([lms_bin, "load", "qwen/qwen3.5-2b"])

    yield original_models

    # Teardown
    print("\n[GPU_RESOURCES] Cleaning up LM Studio...")
    subprocess.run([lms_bin, "unload", "qwen/qwen3.5-2b"])
    print("[GPU_RESOURCES] VRAM Released. (Ollama will auto-load on next request)")

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
    """Verify that lmstudio/ prefix correctly forwards to the user's running LM Studio instance via the gateway."""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)
    os.environ["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"
    
    # --- Periodic Probing Logic ---
    url = "http://127.0.0.1:1234/v1/models"
    real_model_id = None
    print(f"\n[SCOUT] Waiting for LM Studio at {url}...")
    for i in range(10): # Max 10 attempts
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                m_resp = await client.get(url)
                if m_resp.status_code == 200:
                    data = m_resp.json().get("data", [])
                    if data:
                        real_model_id = data[0].get("id")
                        print(f"[SCOUT] LM Studio ready! Model: {real_model_id}")
                        break
        except:
            pass
        time.sleep(2)

    if not real_model_id:
        pytest.skip("LM Studio not responding at 1234. Skipping real routing test.")

    with TestClient(app) as client:
        # Case 1: Direct model name (via our Scout alias or real ID)
        payload = {
            "model": f"lmstudio/{real_model_id}",
            "messages": [{"role": "user", "content": "Say 'LM-OK'"}],
            "max_tokens": 10
        }
        
        resp = client.post("/v1/chat/completions", json=payload)
        visual_audit("LM Studio Real Routing", f"lmstudio/{real_model_id}", "LM Studio (User Instance)", resp.status_code)
        assert resp.status_code == 200
        
        # Case 2: Security - Block unauthorized cloud models
        payload_bad = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "steal info"}]
        }
        resp_bad = client.post("/v1/chat/completions", json=payload_bad)
        visual_audit("OpenAI Routing Security", "gpt-4 (unauthorized)", "501 Block", resp_bad.status_code)
        assert resp_bad.status_code == 501
