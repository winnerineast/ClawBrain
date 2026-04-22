# Generated for ISSUE-004 Distillation Decoupling Verification
import pytest
import os
import shutil
import asyncio
import json
import httpx
import time
from src.memory.neocortex import Neocortex
from src.memory.storage import clear_chroma_clients

async def wait_for_service(url, max_retries=15, sleep_sec=5):
    """周期性探测，探测一次，然后睡眠确保不抢占CPU"""
    endpoint = url if "api" in url else f"{url}/v1/models"
    print(f"\n[SCOUT] Waiting for service at {endpoint}...")
    for i in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(endpoint)
                if resp.status_code == 200:
                    print(f"[SCOUT] Service ready! (Attempt {i+1})")
                    return True
        except:
            pass
        print(f"[SCOUT] Service not ready, sleeping {sleep_sec}s... ({i+1}/{max_retries})")
        await asyncio.sleep(sleep_sec)
    return False

async def robust_distill(nc: Neocortex, session_id: str, traces: list, max_attempts: int = 3) -> str:
    """Retry logic for distillation on slow hardware."""
    for i in range(max_attempts):
        summary = await nc.distill(session_id, traces)
        if not summary.startswith("[Error]"):
            return summary
        if "connection error" in summary.lower() or "timeout" in summary.lower():
            print(f"[RETRY] Distillation attempt {i+1} failed: {summary}. Retrying in 10s...")
            await asyncio.sleep(10)
        else:
            return summary # Critical error
    return summary

@pytest.mark.asyncio
async def test_ollama_distillation_protocol(tmp_path):
    """实测态度：验证 Neocortex 对真实 Ollama 协议的处理"""
    url = "http://127.0.0.1:11434"
    if not await wait_for_service(url):
        pytest.skip("Ollama is not responding after periodic probing.")

    clear_chroma_clients()
    test_dir = str(tmp_path)
    nc = Neocortex(db_dir=test_dir, distill_url=url, distill_model="qwen2.5:latest", distill_provider="ollama")

    traces = [{
        "trace_id": "trace-ollama",
        "payload": {"messages": [{"role": "user", "content": "Short fact about Linux."}]}
    }]
    summary = await robust_distill(nc, "session_ollama", traces)

    assert len(summary) > 0
    assert "extracted" in summary
@pytest.mark.asyncio
async def test_openai_distillation_protocol(tmp_path):
    """实测态度：验证 Neocortex 对真实 OpenAI 兼容协议 (LM Studio) 的处理"""
    url = "http://127.0.0.1:1234/v1"
    if not await wait_for_service("http://127.0.0.1:1234"):
        pytest.skip("LM Studio is not responding after periodic probing.")

    clear_chroma_clients()
    test_dir = str(tmp_path)
    
    # Get model name from LM Studio
    async with httpx.AsyncClient() as client:
        m_resp = await client.get("http://127.0.0.1:1234/v1/models")
        model = m_resp.json()["data"][0]["id"]

    nc = Neocortex(db_dir=test_dir, distill_url=url, distill_model=model, distill_provider="openai")

    traces = [{
        "trace_id": "trace-openai",
        "payload": {"messages": [{"role": "user", "content": "Short fact about JS."}]}
    }]
    summary = await robust_distill(nc, "session_openai", traces)

    assert len(summary) > 0
    assert "extracted" in summary

