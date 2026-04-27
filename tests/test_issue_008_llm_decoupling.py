# Generated from design/model_decoupling.md v1.1
import pytest
import os
import respx
import platform
import json
from httpx import Response
from pathlib import Path

from src.utils.llm_client import HardwareProfiler, LLMFactory, OllamaClient, OpenAIClient
from src.utils.setup_scout import SetupScout
from src.memory.neocortex import Neocortex

# --- Environment Detection ---
CURRENT_OS = platform.system()
IS_MACOS = CURRENT_OS == "Darwin"
IS_LINUX = CURRENT_OS == "Linux"

# --- 1. Real Hardware Intelligence Verification ---

def test_hardware_profiler_real_detection():
    """Verify that hardware detection actually works on this machine without mocks."""
    vram = HardwareProfiler.get_vram_gb()
    tier = HardwareProfiler.get_tier()
    
    assert isinstance(vram, float)
    assert vram >= 0
    assert tier in [1, 2, 3]
    print(f"\n[REAL_HARDWARE] OS: {CURRENT_OS}, VRAM: {vram:.1f}GB, Tier: {tier}")

def test_model_selection_real_logic():
    """Verify model selection based on this machine's actual tier."""
    models = ["llama3:70b", "qwen2.5:32b", "llama3:8b", "phi3:3b", "gemma2:2b"]
    best_model = HardwareProfiler.pick_best_model(models)
    tier = HardwareProfiler.get_tier()
    
    assert best_model is not None
    if tier == 1:
        assert "70b" in best_model.lower() or "32b" in best_model.lower()
    elif tier == 2:
        assert "8b" in best_model.lower() or "32b" in best_model.lower() # 32b might be picked as fallback if 14b missing
    else:
        assert "3b" in best_model.lower() or "2b" in best_model.lower()

# --- 2. OS-Specific Provider Discovery Verification ---

@pytest.mark.asyncio
@respx.mock
async def test_setup_scout_ollama_discovery():
    """Verify Ollama discovery (Relevant for both macOS and Ubuntu)."""
    respx.get("http://localhost:11434/api/tags").mock(return_value=Response(200, json={
        "models": [{"name": "test-ollama-model"}]
    }))
    
    scout = SetupScout()
    found = await scout.probe_ollama()
    assert found is True
    assert scout.findings["distill_provider"] == "ollama"

@pytest.mark.skipif(not IS_MACOS, reason="OMLX and LM Studio preference testing is macOS specific per instruction")
@pytest.mark.asyncio
@respx.mock
async def test_setup_scout_macos_preferences():
    """Verify macOS prefers OMLX/LM Studio over Ollama."""
    # Mock all three services being online
    respx.get("http://localhost:11434/api/tags").mock(return_value=Response(200, json={"models": [{"name": "ollama-m"}]}))
    respx.get("http://localhost:1234/v1/models").mock(return_value=Response(200, json={"data": [{"id": "lms-m"}]}))
    respx.get("http://localhost:8080/v1/models").mock(return_value=Response(200, json={"data": [{"id": "omlx-m"}]}))
    
    scout = SetupScout()
    # On macOS, we probe OMLX and LMS, they should take precedence
    await scout.probe_ollama()
    await scout.probe_lmstudio()
    await scout.probe_omlx()
    
    # OMLX has highest preference in code for macOS
    assert scout.findings["distill_provider"] == "openai"
    assert "8080" in scout.findings["distill_url"]

@pytest.mark.skipif(IS_MACOS, reason="Testing Ubuntu-specific simple provider logic")
@pytest.mark.asyncio
@respx.mock
async def test_setup_scout_ubuntu_logic():
    """Verify Ubuntu behavior (Ollama priority)."""
    respx.get("http://localhost:11434/api/tags").mock(return_value=Response(200, json={"models": [{"name": "ollama-m"}]}))
    
    scout = SetupScout()
    await scout.probe_ollama()
    
    assert scout.findings["distill_provider"] == "ollama"
    assert "11434" in scout.findings["distill_url"]

# --- 3. Unified Client Abstraction Verification ---

@pytest.mark.asyncio
@respx.mock
async def test_llm_factory_and_client_standardization():
    """Verify that clients format correctly regardless of platform."""
    # 1. Test Ollama branch
    respx.post("http://localhost:11434/api/generate").mock(return_value=Response(200, json={"response": "O"}))
    ollama_client = LLMFactory.get_client("ollama", "http://localhost:11434", "m1")
    res1 = await ollama_client.generate("Hi")
    assert res1 == "O"
    
    # 2. Test OpenAI/LMS/OMLX branch
    respx.post("http://localhost:8080/chat/completions").mock(return_value=Response(200, json={
        "choices": [{"message": {"content": "X"}}]
    }))
    openai_client = LLMFactory.get_client("openai", "http://localhost:8080", "m2")
    res2 = await openai_client.generate("Hi")
    assert res2 == "X"
