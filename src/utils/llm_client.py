# Generated from design/model_decoupling.md v1.1
import os
import httpx
import logging
import platform
import subprocess
from typing import List, Dict, Any, Optional
from src.utils.config import get_env

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("GATEWAY.LLM")

class HardwareProfiler:
    """Utility to detect system resources and determine optimal model tiers."""
    
    @staticmethod
    def get_vram_gb() -> float:
        system = platform.system()
        total_ram_gb = 0
        vram_gb = 0

        # 1. Detect System RAM
        if psutil:
            total_ram_gb = psutil.virtual_memory().total / (1024**3)
        elif system == "Darwin":
            try:
                res = subprocess.check_output(["sysctl", "hw.memsize"])
                total_ram_gb = int(res.decode().split(":")[1].strip()) / (1024**3)
            except: pass
        
        # 2. Detect VRAM
        if system == "Darwin" and platform.machine() == "arm64":
            vram_gb = total_ram_gb * 0.7 # Apple Silicon Unified Memory
        elif system == "Linux":
            try:
                res = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"])
                vram_gb = int(res.decode().strip()) / 1024
            except:
                vram_gb = total_ram_gb * 0.5 # CPU fallback
        
        return vram_gb

    @staticmethod
    def get_tier() -> int:
        vram = HardwareProfiler.get_vram_gb()
        if vram >= 30: return 1
        if vram >= 15: return 2
        return 3

    @staticmethod
    def pick_best_model(models: List[str]) -> Optional[str]:
        if not models: return None
        tier = HardwareProfiler.get_tier()
        
        if tier == 1: targets = ["70b", "32b", "30b", "27b"]
        elif tier == 2: targets = ["14b", "13b", "8b", "7b"]
        else: targets = ["3b", "2b", "1b", "0.5b"]
            
        fallback_targets = ["8b", "7b", "3b"] if tier <= 2 else ["3b", "latest"]

        for t in targets + fallback_targets:
            for m in models:
                if t in m.lower(): return m
        return models[0]

class LLMClient:
    """Base class for all LLM providers."""
    _client_instance: Optional[httpx.AsyncClient] = None

    def __init__(self, url: str, model: str, api_key: str = "", timeout: float = 60.0):
        self.url = url.rstrip('/')
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    async def generate(self, prompt: str, system: str = None) -> str:
        raise NotImplementedError

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        raise NotImplementedError

    @classmethod
    async def aclose(cls):
        if cls._client_instance:
            try:
                if not cls._client_instance.is_closed:
                    await cls._client_instance.aclose()
            except RuntimeError:
                # Loop might already be closed
                pass
            finally:
                cls._client_instance = None

class OllamaClient(LLMClient):
    """Ollama-specific implementation."""
    async def generate(self, prompt: str, system: str = None) -> str:
        url = f"{self.url}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if system: payload["system"] = system
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "")
        except Exception as e:
            logger.error(f"[OLLAMA] Generation failed: {e}")
            return f"[Error] {e}"

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        url = f"{self.url}/api/chat"
        payload = {"model": self.model, "messages": messages, "stream": False}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"[OLLAMA] Chat failed: {e}")
            return f"[Error] {e}"

class OpenAIClient(LLMClient):
    """OpenAI-compatible implementation (used by LM Studio, OMLX)."""
    async def generate(self, prompt: str, system: str = None) -> str:
        messages = []
        if system: messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages)

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        url = f"{self.url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0.1,  # Ensure determinism
            "max_tokens": 1000
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                msg = resp.json().get("choices", [{}])[0].get("message", {})
                content = msg.get("content", "")
                if not content and "reasoning_content" in msg:
                    content = msg["reasoning_content"]
                print(f"[DEBUG_LLM] Provider: {self.url}, Model: {self.model}, Response: '{content[:50]}...'")
                return content
        except Exception as e:
            logger.error(f"[OPENAI-COMPAT] Chat failed: {e}")
            return f"[Error] {e}"

class LLMFactory:
    """Factory for creating LLM clients."""
    @staticmethod
    def get_client(provider: str, url: str, model: str, api_key: str = "", timeout: float = 60.0) -> LLMClient:
        if provider.lower() == "ollama":
            return OllamaClient(url, model, api_key, timeout)
        else:
            return OpenAIClient(url, model, api_key, timeout)

    @staticmethod
    def from_env() -> LLMClient:
        """Create a client from environment variables."""
        provider = get_env("CLAWBRAIN_DISTILL_PROVIDER", "ollama")
        url = get_env("CLAWBRAIN_DISTILL_URL", "http://localhost:11434")
        model = get_env("CLAWBRAIN_DISTILL_MODEL", "gemma4:e4b")
        api_key = get_env("CLAWBRAIN_DISTILL_API_KEY", "")
        return LLMFactory.get_client(provider, url, model, api_key)
