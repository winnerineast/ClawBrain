# Generated for ISSUE-004 Distillation Decoupling Verification
import pytest
import os
import shutil
import asyncio
import json
import respx
from httpx import Response
from src.memory.neocortex import Neocortex
from src.memory.storage import clear_chroma_clients

@pytest.mark.asyncio
@respx.mock
async def test_ollama_distillation_protocol(tmp_path):
    """Verify Neocortex correctly calls Ollama /api/generate."""
    clear_chroma_clients()
    url = "http://mock-ollama:11434"
    model = "mock-gemma"
    test_dir = str(tmp_path)
    
    nc = Neocortex(db_dir=test_dir, distill_url=url, distill_model=model, distill_provider="ollama")
    
    # Mock Ollama response
    route = respx.post(f"{url}/api/generate").mock(return_value=Response(200, json={"response": "Ollama Summary"}))
    
    traces = [{"stimulus": {"messages": [{"role": "user", "content": "hello"}]}}]
    summary = await nc.distill("session_ollama", traces)
    
    assert summary == "Ollama Summary"
    assert route.called
    # Check payload
    sent_json = json.loads(route.calls.last.request.content)
    assert sent_json["model"] == model
    assert "hello" in sent_json["prompt"]
    
    # Verify persistence
    assert nc.get_summary("session_ollama") == "Ollama Summary"

@pytest.mark.asyncio
@respx.mock
async def test_openai_distillation_protocol(tmp_path):
    """Verify Neocortex correctly calls OpenAI-compatible /chat/completions."""
    clear_chroma_clients()
    url = "http://mock-openai:8080/v1"
    model = "mock-gpt"
    test_dir = str(tmp_path)
    
    nc = Neocortex(db_dir=test_dir, distill_url=url, distill_model=model, distill_provider="openai")
    
    # Mock OpenAI response
    route = respx.post(f"{url}/chat/completions").mock(return_value=Response(200, json={
        "choices": [{"message": {"content": "OpenAI Summary"}}]
    }))
    
    traces = [{"stimulus": {"messages": [{"role": "user", "content": "hello"}]}}]
    summary = await nc.distill("session_openai", traces)
    
    assert summary == "OpenAI Summary"
    assert route.called
    # Check payload
    sent_json = json.loads(route.calls.last.request.content)
    assert sent_json["model"] == model
    assert sent_json["messages"][1]["content"].find("hello") != -1
    
    # Verify persistence
    assert nc.get_summary("session_openai") == "OpenAI Summary"

@pytest.mark.asyncio
async def test_config_priority(tmp_path):
    """Verify environment variables override constructor args."""
    clear_chroma_clients()
    test_dir = str(tmp_path)
    os.environ["CLAWBRAIN_DISTILL_URL"] = "http://env-url"
    os.environ["CLAWBRAIN_DISTILL_MODEL"] = "env-model"
    os.environ["CLAWBRAIN_DISTILL_PROVIDER"] = "env-provider"
    
    try:
        nc = Neocortex(db_dir=test_dir, distill_url="http://arg-url", distill_model="arg-model", distill_provider="arg-provider")
        assert nc.distill_url == "http://env-url"
        assert nc.distill_model == "env-model"
        assert nc.distill_provider == "env-provider"
    finally:
        del os.environ["CLAWBRAIN_DISTILL_URL"]
        del os.environ["CLAWBRAIN_DISTILL_MODEL"]
        del os.environ["CLAWBRAIN_DISTILL_PROVIDER"]
