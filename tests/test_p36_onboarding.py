# Generated from design/utils_onboarding.md v1.1
import pytest
import os
import respx
import platform
import httpx
from httpx import Response
from pathlib import Path
from src.utils.setup_scout import SetupScout
from src.utils.doctor import SystemDoctor

@pytest.mark.asyncio
async def test_scout_cross_platform_correction(tmp_path, monkeypatch):
    """Verify that invalid OS paths in .env are corrected."""
    # Ensure we use the tmp_path for the .env file
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    
    current_os = platform.system()
    if current_os == "Darwin":
        legacy_path = "/home/user/data"
    else:
        legacy_path = "/Users/user/data"
        
    expected_path = str(tmp_path / "data")

    env_file.write_text(f"CLAWBRAIN_DB_DIR={legacy_path}\n")
    
    scout = SetupScout()
    scout.findings["db_dir"] = expected_path
    
    scout.generate_env()
    
    content = env_file.read_text()
    assert f'CLAWBRAIN_DB_DIR="{expected_path}"' in content
    assert legacy_path not in content

@pytest.mark.asyncio
@respx.mock
async def test_scout_ollama_detection():
    """Verify scout correctly identifies Ollama and its models."""
    scout = SetupScout()
    
    # Mock Ollama response
    respx.get("http://localhost:11434/api/tags").mock(return_value=Response(200, json={
        "models": [{"name": "mock-gemma:latest"}]
    }))
    # Mock LM Studio fail
    respx.get("http://localhost:1234/v1/models").mock(return_value=Response(500))
    
    await scout.probe_ollama()
    await scout.probe_lmstudio()
    
    assert scout.findings["distill_provider"] == "ollama"
    assert scout.findings["distill_model"] == "mock-gemma:latest"
    assert scout.findings["distill_url"] == "http://localhost:11434"

@pytest.mark.asyncio
@respx.mock
async def test_scout_lmstudio_detection():
    """Verify scout correctly identifies LM Studio when Ollama is absent."""
    scout = SetupScout()
    
    # Mock Ollama fail
    respx.get("http://localhost:11434/api/tags").mock(side_effect=httpx.ConnectError("Refused"))
    # Mock LM Studio success
    respx.get("http://localhost:1234/v1/models").mock(return_value=Response(200, json={
        "data": [{"id": "mock-llama-3"}]
    }))
    
    await scout.probe_ollama()
    await scout.probe_lmstudio()
    
    assert scout.findings["distill_provider"] == "openai"
    assert scout.findings["distill_model"] == "mock-llama-3"
    assert scout.findings["distill_url"] == "http://localhost:1234"

@pytest.mark.asyncio
@respx.mock
async def test_doctor_connectivity():
    """Verify that doctor can detect online/offline services."""
    # Mock LM Studio success
    respx.get("http://localhost:1234/v1/models").mock(return_value=Response(200, json={"data": []}))
    # Mock Ollama fail
    respx.get("http://localhost:11434/api/tags").mock(side_effect=httpx.ConnectError("Refused"))
    
    doctor = SystemDoctor()
    status = await doctor.check_connectivity()

    assert status["lmstudio"] == "ONLINE"
    assert status["ollama"] == "OFFLINE"

@pytest.mark.asyncio
@respx.mock
async def test_doctor_llm_verification(monkeypatch):
    """Verify doctor can perform a test generation with the backend."""
    monkeypatch.setenv("CLAWBRAIN_DISABLE_COGNITIVE_JUDGE", "true")
    # Mock Judge (Cognitive Judge v1.4)
    respx.post("http://localhost:1234/chat/completions").mock(return_value=Response(200, json={
        "choices": [{"message": {"content": "YES"}}]
    }))
    
    doctor = SystemDoctor()
    res = await doctor.verify_llm()
    assert res is True

@pytest.mark.asyncio
async def test_scout_env_generation(tmp_path):
    """Verify .env generation is idempotent and respects findings."""
    os.chdir(tmp_path)
    scout = SetupScout()
    scout.findings = {
        "distill_url": "http://test-url",
        "distill_model": "test-model",
        "distill_provider": "test-provider",
        "vault_path": "/test/vault",
        "db_dir": str(tmp_path / "data")
    }
    
    # 1. First generation
    scout.generate_env()
    env_file = tmp_path / ".env"
    assert env_file.exists()
    content = env_file.read_text()
    assert 'CLAWBRAIN_DISTILL_URL="http://test-url"' in content
    
    # 2. Idempotency: Manually change a value
    env_file.write_text('CLAWBRAIN_MAX_CONTEXT_CHARS="5000"\nCLAWBRAIN_DISTILL_MODEL="manual-model"\n')
    scout.generate_env()
    content_v2 = env_file.read_text()
    
    # Should keep manual-model and 5000
    assert 'CLAWBRAIN_DISTILL_MODEL="manual-model"' in content_v2
    assert 'CLAWBRAIN_MAX_CONTEXT_CHARS="5000"' in content_v2
    # Should still have the others
    assert 'CLAWBRAIN_VAULT_PATH="/test/vault"' in content_v2
    assert 'CLAWBRAIN_DISTILL_URL="http://test-url"' in content_v2
