# Generated from design/model_decoupling.md v1.8
import os
import httpx
import logging
import platform
import subprocess
import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

from src.utils.config import get_env

logger = logging.getLogger("GATEWAY.LLM")

class HardwareProfiler:
    """Profiles system resources to guide model selection."""
    @staticmethod
    def get_vram_gb() -> float:
        system = platform.system()
        total_ram_gb = 0
        vram_gb = 0
        if psutil:
            total_ram_gb = psutil.virtual_memory().total / (1024**3)
        elif system == "Darwin":
            try:
                res = subprocess.check_output(["sysctl", "hw.memsize"])
                total_ram_gb = int(res.decode().split(":")[1].strip()) / (1024**3)
            except: pass
        if system == "Darwin" and platform.machine() == "arm64":
            vram_gb = total_ram_gb * 0.7 
        elif system == "Linux":
            try:
                res = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"])
                vram_gb = int(res.decode().strip()) / 1024
            except: vram_gb = total_ram_gb * 0.5 
        return vram_gb

    @staticmethod
    def get_tier() -> int:
        vram = HardwareProfiler.get_vram_gb()
        if vram >= 30: return 1
        if vram >= 15: return 2
        return 3

class BaseClient:
    def __init__(self, url: str, model: str, api_key: str = "", timeout: float = 60.0):
        self.url = url.rstrip('/')
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.size_b = self._parse_size(model)

    def _parse_size(self, name: str) -> float:
        match = re.search(r'([0-9.]+)[Bb]', name)
        return float(match.group(1)) if match else 7.0

class EmbedClient(BaseClient):
    """Unified interface for text embeddings."""
    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        raise NotImplementedError
    
    def embed_sync(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Synchronous embedding for ChromaDB compatibility."""
        raise NotImplementedError

class OllamaEmbedClient(EmbedClient):
    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        url = f"{self.url}/api/embed"
        payload = {"model": self.model, "input": texts}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                return resp.json().get("embeddings", [])
        except Exception as e:
            logger.error(f"[LLM_ERR] Ollama embed failed: {e}")
            return []

    def embed_sync(self, texts: List[str], **kwargs) -> List[List[float]]:
        url = f"{self.url}/api/embed"
        payload = {"model": self.model, "input": texts}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload)
                return resp.json().get("embeddings", [])
        except Exception as e:
            logger.error(f"[LLM_ERR] Ollama sync embed failed: {e}")
            return []

class OpenAIEmbedClient(EmbedClient):
    """v1.11: Support for OpenAI-compatible embedding models."""
    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        url = f"{self.url}/v1/embeddings"
        payload = {"model": self.model, "input": texts}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                data = resp.json().get("data", [])
                return [d["embedding"] for d in data]
        except Exception as e:
            logger.error(f"[LLM_ERR] OpenAI embed failed: {e}")
            return []

    def embed_sync(self, texts: List[str], **kwargs) -> List[List[float]]:
        url = f"{self.url}/v1/embeddings"
        payload = {"model": self.model, "input": texts}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                data = resp.json().get("data", [])
                return [d["embedding"] for d in data]
        except Exception as e:
            logger.error(f"[LLM_ERR] OpenAI sync embed failed: {e}")
            return []

class ChatClient(BaseClient):
    """Unified interface for text generation."""
    async def generate(self, prompt: str, system: str = None, **kwargs) -> str:
        raise NotImplementedError
    
    async def check_health(self) -> bool:
        try:
            res = await self.generate("Say 'OK'", max_tokens=10)
            return "OK" in res.upper()
        except: return False

class OllamaChatClient(ChatClient):
    async def generate(self, prompt: str, system: str = None, **kwargs) -> str:
        url = f"{self.url}/api/generate"
        payload = {
            "model": self.model, "prompt": prompt, "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.1),
                "num_predict": kwargs.get("max_tokens", 2000) # Increased buffer
            }
        }
        if system: payload["system"] = system
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                return resp.json().get("response", "")
        except: return ""

class OpenAIChatClient(ChatClient):
    """v1.8: Reasoning-aware client for modern local LLMs."""
    async def generate(self, prompt: str, system: str = None, **kwargs) -> str:
        url = f"{self.url}/v1/chat/completions"
        msgs = []
        if system: msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model, 
            "messages": msgs, 
            "stream": False, 
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 2000) # Increased buffer
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                data = resp.json().get("choices", [{}])[0].get("message", {})
                
                # v1.8: INTELLIGENT REASONING EXTRACTION
                # Capture both thinking process and final answer
                content = data.get("content", "")
                reasoning = data.get("reasoning_content", "")
                
                final_res = content or reasoning
                if not final_res:
                    logger.warning(f"[LLM] {self.model} returned empty content and reasoning.")
                return final_res
        except Exception as e:
            logger.error(f"[LLM_ERR] OpenAI call failed: {e}")
            return ""

class LLMScheduler:
    def __init__(self):
        self.chat_pool: List[ChatClient] = []
        self.embed_pool: List[EmbedClient] = []

    async def scan(self):
        hosters = [
            ("openai", "http://localhost:8080"),
            ("openai", "http://localhost:1234"),
            ("ollama", "http://localhost:11434"),
        ]
        self.chat_pool = []
        for provider, url in hosters:
            try:
                path = "/api/tags" if provider == "ollama" else "/v1/models"
                async with httpx.AsyncClient(timeout=1.0) as client:
                    resp = await client.get(f"{url}{path}")
                    if resp.status_code == 200:
                        data = resp.json()
                        models = [m["name"] for m in data.get("models", [])] if provider == "ollama" else [m["id"] for m in data.get("data", [])]
                        for m in models:
                            if "embed" in m.lower():
                                self.embed_pool.append(LLMFactory.get_embed_client(provider, url, m))
                            else:
                                self.chat_pool.append(LLMFactory.get_chat_client(provider, url, m))
            except: continue

    def select_best_chat(self, role: str = "brain") -> Union[ChatClient, EmbedClient]:
        if role == "embedding":
            if self.embed_pool:
                return self.embed_pool[0]
            # fallback to default
            return LLMFactory.get_embed_client("ollama", get_env("CLAWBRAIN_DISTILL_URL", "http://localhost:11434"), "nomic-embed-text")

        if not self.chat_pool: return LLMFactory.from_env()
        sorted_by_size = sorted(self.chat_pool, key=lambda x: x.size_b)
        
        tier = HardwareProfiler.get_tier()
        if role == "worker":
            # Tier-aware worker selection (7B+ preferred for logic)
            if tier <= 2:
                eligible = [c for c in sorted_by_size if 7 <= c.size_b <= 15]
                if eligible: return eligible[0]
            return sorted_by_size[0]
        
        # Brain selection
        if tier == 1: eligible = [c for c in sorted_by_size if c.size_b <= 72]
        elif tier == 2: eligible = [c for c in sorted_by_size if c.size_b <= 15]
        else: return sorted_by_size[0]
        return eligible[-1] if eligible else sorted_by_size[0]

class LLMFactory:
    @staticmethod
    def get_embed_client(provider: str, url: str, model: str, api_key: str = "") -> EmbedClient:
        if provider.lower() == "ollama": return OllamaEmbedClient(url, model, api_key)
        if provider.lower() == "openai": return OpenAIEmbedClient(url, model, api_key)
        return OllamaEmbedClient(url, model, api_key)  # Fallback to Ollama logic for generic embeds for now

    @staticmethod
    def get_chat_client(provider: str, url: str, model: str, api_key: str = "") -> ChatClient:
        if provider.lower() == "ollama": return OllamaChatClient(url, model, api_key)
        return OpenAIChatClient(url, model, api_key)

    @staticmethod
    def from_env() -> ChatClient:
        return LLMFactory.get_chat_client(get_env("CLAWBRAIN_DISTILL_PROVIDER", "ollama"), 
                                        get_env("CLAWBRAIN_DISTILL_URL", "http://localhost:11434"), 
                                        get_env("CLAWBRAIN_DISTILL_MODEL", "gemma4:e4b"))

    @staticmethod
    async def get_intelligent_scheduler() -> LLMScheduler:
        s = LLMScheduler(); await s.scan(); return s
