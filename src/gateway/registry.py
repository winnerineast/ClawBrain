# Generated from design/config.md v1.2
import os
import json
import logging
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv
from src.utils.config import get_env

load_dotenv()
logger = logging.getLogger("GATEWAY")

class ProviderConfig:
    def __init__(self, name: str, base_url: str, protocol: str, api_key: str = ""):
        self.name = name
        self.base_url = base_url
        self.protocol = protocol
        self.api_key = api_key

class ProviderRegistry:
    """
    Intelligent Routing Registry. Supports hot-extension via environment variables.
    Rule 14: Environment-aware dynamic routing to avoid hardcoded port conflicts.
    """
    def __init__(self):
        distill_url = get_env("CLAWBRAIN_DISTILL_URL", "http://localhost:11434")
        distill_provider = get_env("CLAWBRAIN_DISTILL_PROVIDER", "ollama")
        
        # 1. Base Service Configuration
        self.providers: Dict[str, ProviderConfig] = {
            "ollama":      ProviderConfig("ollama",      "http://localhost:11434", "ollama"),
            "lmstudio":    ProviderConfig("lmstudio",    "http://localhost:1234",  "openai"),
            "omlx":        ProviderConfig("omlx",        "http://localhost:8080",  "openai"),
            "openai":      ProviderConfig("openai",      "https://api.openai.com",                    "openai"),
            "deepseek":    ProviderConfig("deepseek",    "https://api.deepseek.com",                  "openai"),
            "anthropic":   ProviderConfig("anthropic",   "https://api.anthropic.com",                 "anthropic"),
            "google":      ProviderConfig("google",      "https://generativelanguage.googleapis.com", "google"),
        }

        # 2. Dynamic Override: Link the active distillation provider to the discovered URL
        if distill_provider in self.providers:
            self.providers[distill_provider].base_url = distill_url
            logger.info(f"[REGISTRY] Local provider '{distill_provider}' dynamically linked to {distill_url}")

        # 3. Known Models Whitelist (Routing without explicit prefixes)
        self.known_no_prefix_models = {
            "gemma4:e4b":      "ollama",
            "gemma4:31b":      "ollama",
            "qwen2.5:latest":  "ollama",
            "gpt-4":           "openai",
            "gpt-3.5-turbo":   "openai",
        }

        # P16: Load extra configurations from environment
        self._load_extras()

    def _load_extras(self):
        extra_providers_json = get_env("CLAWBRAIN_EXTRA_PROVIDERS")
        if extra_providers_json:
            try:
                extras = json.loads(extra_providers_json)
                for name, cfg in extras.items():
                    self.providers[name] = ProviderConfig(name, cfg["base_url"], cfg.get("protocol", "openai"))
            except Exception as e:
                logger.warning(f"[REGISTRY] CLAWBRAIN_EXTRA_PROVIDERS parse failed: {e}")

        extra_models_json = get_env("CLAWBRAIN_LOCAL_MODELS")
        if extra_models_json:
            try:
                self.known_no_prefix_models.update(json.loads(extra_models_json))
            except Exception as e:
                logger.warning(f"[REGISTRY] CLAWBRAIN_LOCAL_MODELS parse failed: {e}")

    def resolve_provider(self, full_model_name: str) -> Tuple[Optional[str], Optional[ProviderConfig]]:
        """
        Resolve provider name and config from model name.
        Rule: Strict resolution with intelligent fallback for discovered local models.
        """
        # 1. Explicit prefix matching (e.g., ollama/llama3)
        if "/" in full_model_name:
            prefix = full_model_name.split("/")[0].lower()
            if prefix in self.providers:
                return prefix, self.providers[prefix]
            return None, None

        # 2. Local whitelist matching
        if full_model_name in self.known_no_prefix_models:
            p_name = self.known_no_prefix_models[full_model_name]
            return p_name, self.providers[p_name]

        # 3. Intelligent Fallback: If it's a known non-cloud model string OR if we are in a discovered local env,
        # fallback to the main distillation provider.
        # This prevents 501 for local models that haven't been explicitly whitelisted yet.
        distill_p = get_env("CLAWBRAIN_DISTILL_PROVIDER")
        if distill_p:
            # We only fallback for models that don't look like generic cloud IDs
            if not full_model_name.startswith("gpt-") and not full_model_name.startswith("claude-"):
                return distill_p, self.providers.get(distill_p)

        return None, None
