# Generated from design/model_decoupling.md v1.2
import pytest
import os
import respx
import platform
import json
from httpx import Response
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils.llm_client import HardwareProfiler, LLMFactory, OllamaChatClient, OpenAIChatClient, EmbedClient, OllamaEmbedClient
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
    from src.utils.llm_client import LLMScheduler, LLMFactory
    scheduler = LLMScheduler()
    scheduler.chat_pool = [
        LLMFactory.get_chat_client("ollama", "url", "llama3:70b"),
        LLMFactory.get_chat_client("ollama", "url", "qwen3.6:35b"),
        LLMFactory.get_chat_client("ollama", "url", "qwen3.5:9b"),
        LLMFactory.get_chat_client("ollama", "url", "phi3:3b"),
    ]
    
    with patch("src.utils.llm_client.HardwareProfiler.get_tier") as mock_tier:
        mock_tier.return_value = 1
        best = scheduler.select_best_chat(role="brain")
        assert "35b" in best.model.lower() or "70b" in best.model.lower()
        
        mock_tier.return_value = 2
        best = scheduler.select_best_chat(role="brain")
        assert "9b" in best.model.lower()

# --- 2. Advanced Parameter Pass-through Verification ---

@pytest.mark.asyncio
@respx.mock
async def test_ollama_parameter_translation():
    """Verify that OllamaClient correctly translates kwargs into 'options'."""
    respx.post("http://localhost:11434/api/generate").mock(return_value=Response(200, json={"response": "OK"}))
    
    client = OllamaChatClient("http://localhost:11434", "m1")
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
    
    client = OpenAIChatClient("http://localhost:1234", "m2")
    res = await client.generate("Hi")
    assert res == "V1 OK"

# --- 3. Cross-OS Auto-Configuration Verification (No Mocking Logic) ---

def test_llm_factory_os_defaults():
    """Verify that LLMFactory chooses proper defaults when env is missing."""
    # We use a clean env state for this test
    with patch.dict(os.environ, {}, clear=True), \
         patch("src.utils.config.get_env", return_value=None):
        
        client = LLMFactory.from_env()
        assert isinstance(client, OllamaChatClient)
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

def test_llmscheduler_embedding_role():
    from src.utils.llm_client import LLMScheduler
    scheduler = LLMScheduler()
    scheduler.embed_pool = [OllamaEmbedClient("http://localhost:11434", "nomic-embed")]
    
    best = scheduler.select_best_chat(role="embedding")
    assert isinstance(best, EmbedClient)
    assert best.model == "nomic-embed"
