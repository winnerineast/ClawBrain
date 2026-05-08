# Generated from design/model_decoupling.md v1.2
import pytest
import os
import respx
import platform
import json
from httpx import Response
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils.llm_client import HardwareProfiler, LLMFactory, OllamaClient, OpenAIClient
from src.utils.config import get_env

# --- Environment Detection ---
CURRENT_OS = platform.system()
IS_MACOS = CURRENT_OS == "Darwin"
IS_LINUX = CURRENT_OS == "Linux"

# --- 1. Enhanced Hardware Intelligence Verification ---

def test_hardware_profiler_tier_logic():
    """Verify tier assignment based on effective VRAM/Unified Memory."""
    with patch("src.utils.llm_client.HardwareProfiler.get_vram_gb") as mock_vram:
        # Tier 1: High (e.g., 64GB)
        mock_vram.return_value = 64.0
        assert HardwareProfiler.get_tier() == 1
        
        # Tier 2: Medium (e.g., 24GB)
        mock_vram.return_value = 24.0
        assert HardwareProfiler.get_tier() == 2
        
        # Tier 3: Low (e.g., 8GB)
        mock_vram.return_value = 8.0
        assert HardwareProfiler.get_tier() == 3

def test_model_selection_v1_2_logic():
    """Verify model selection picks optimized versions (35b, 9b, etc.)."""
    models = ["llama3:70b", "qwen3.6:35b", "qwen3.5:9b", "phi3:3b"]
    
    with patch("src.utils.llm_client.HardwareProfiler.get_tier") as mock_tier:
        mock_tier.return_value = 1
        best = HardwareProfiler.pick_best_model(models)
        assert "35b" in best.lower() or "70b" in best.lower()
        
        mock_tier.return_value = 2
        best = HardwareProfiler.pick_best_model(models)
        assert "9b" in best.lower()

# --- 2. Advanced Parameter Pass-through Verification ---

@pytest.mark.asyncio
@respx.mock
async def test_ollama_parameter_translation():
    """Verify that OllamaClient correctly translates kwargs into 'options'."""
    respx.post("http://localhost:11434/api/generate").mock(return_value=Response(200, json={"response": "OK"}))
    
    client = OllamaClient("http://localhost:11434", "m1")
    await client.generate("Hi", temperature=0.7, max_tokens=500)
    
    sent_json = json.loads(respx.calls.last.request.content)
    assert sent_json["options"]["temperature"] == 0.7
    assert sent_json["options"]["num_predict"] == 500

@pytest.mark.asyncio
@respx.mock
async def test_openai_v1_path_alignment():
    """Verify that OpenAIClient uses the mandatory /v1/ prefix."""
    # This specifically addresses the LM Studio bug found in the logs
    respx.post("http://localhost:1234/v1/chat/completions").mock(return_value=Response(200, json={
        "choices": [{"message": {"content": "V1 OK"}}]
    }))
    
    client = OpenAIClient("http://localhost:1234", "m2")
    res = await client.generate("Hi")
    assert res == "V1 OK"

# --- 3. Cross-OS Auto-Configuration Verification (No Mocking Logic) ---

@pytest.mark.asyncio
def test_llm_factory_os_defaults():
    """Verify that LLMFactory chooses proper defaults based on real OS when env is missing."""
    # We use a clean env state for this test
    with patch.dict(os.environ, {}, clear=True), \
         patch("src.utils.config.get_env", return_value=None):
        
        client = LLMFactory.from_env()
        
        if IS_MACOS:
            # On macOS, it should default to OpenAI-compatible (OMLX) on 8080
            assert isinstance(client, OpenAIClient)
            assert "8080" in client.url
        else:
            # On Linux/Other, it should default to Ollama on 11434
            assert isinstance(client, OllamaClient)
            assert "11434" in client.url

# --- 4. The "Gold Standard" Cross-Platform Scenario ---

@pytest.mark.asyncio
@respx.mock
async def test_gold_standard_mac_omlx_config():
    """Verify the exact requested macOS configuration: OMLX + Qwen3.6-35B."""
    config = {
        "DARWIN_CLAWBRAIN_DISTILL_PROVIDER": "openai",
        "DARWIN_CLAWBRAIN_DISTILL_URL": "http://localhost:8080",
        "DARWIN_CLAWBRAIN_DISTILL_MODEL": "Qwen3.6-35B-A3B-4bit"
    }
    
    with patch.dict(os.environ, config), patch("platform.system", return_value="Darwin"):
        respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=Response(200, json={
            "choices": [{"message": {"content": "Reasoned via OMLX"}}]
        }))
        
        client = LLMFactory.from_env()
        assert client.url == "http://localhost:8080"
        assert client.model == "Qwen3.6-35B-A3B-4bit"
        
        res = await client.generate("Question")
        assert res == "Reasoned via OMLX"

@pytest.mark.asyncio
@respx.mock
async def test_gold_standard_ubuntu_ollama_config():
    """Verify the exact requested Ubuntu configuration: Ollama + Qwen3.6-35B."""
    config = {
        "LINUX_CLAWBRAIN_DISTILL_PROVIDER": "ollama",
        "LINUX_CLAWBRAIN_DISTILL_URL": "http://localhost:11434",
        "LINUX_CLAWBRAIN_DISTILL_MODEL": "qwen3.6-35b"
    }
    
    with patch.dict(os.environ, config), patch("platform.system", return_value="Linux"):
        respx.post("http://localhost:11434/api/generate").mock(return_value=Response(200, json={"response": "Reasoned via Ollama"}))
        
        client = LLMFactory.from_env()
        assert client.url == "http://localhost:11434"
        assert client.model == "qwen3.6-35b"
        
        res = await client.generate("Question")
        assert res == "Reasoned via Ollama"
