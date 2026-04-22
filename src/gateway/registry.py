# Generated from design/config.md v1.0
import os
import json
import logging
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("GATEWAY")

class ProviderConfig:
    def __init__(self, name: str, base_url: str, protocol: str = "openai", api_key: str = None):
        self.name = name
        self.base_url = base_url
        self.protocol = protocol
        self.api_key = api_key

class ProviderRegistry:
    """
    Intelligent Routing Registry. Supports hot extensions via environment variables.
    """
    def __init__(self):
        # Phase 16: Environment Variable Provider Extensions
        extra_providers_json = os.getenv("CLAWBRAIN_EXTRA_PROVIDERS", "{}")
        try:
            extra_providers = json.loads(extra_providers_json)
        except:
            logger.warning("[REGISTRY] Malformed CLAWBRAIN_EXTRA_PROVIDERS. Using defaults.")
            extra_providers = {}

        self.providers = {
            "openai": ProviderConfig("openai", "https://api.openai.com/v1", "openai"),
            "anthropic": ProviderConfig("anthropic", "https://api.anthropic.com/v1", "anthropic"),
            "google": ProviderConfig("google", "https://generativelanguage.googleapis.com/v1beta", "google"),
            "ollama": ProviderConfig("ollama", "http://127.0.0.1:11434", "ollama"),
            "lmstudio": ProviderConfig("lmstudio", "http://127.0.0.1:1234/v1", "openai"),
            "mistral": ProviderConfig("mistral", "https://api.mistral.ai/v1", "openai"),
            "together": ProviderConfig("together", "https://api.together.xyz/v1", "openai"),
            "deepseek": ProviderConfig("deepseek", "https://api.deepseek.com", "openai"),
        }
        
        # Inject extra providers
        for name, config in extra_providers.items():
            self.providers[name] = ProviderConfig(
                name, 
                config.get("base_url"), 
                config.get("protocol", "openai"),
                config.get("api_key")
            )

        # Phase 16: Environment Variable Local Model Whitelist
        extra_models_json = os.getenv("CLAWBRAIN_LOCAL_MODELS", "{}")
        try:
            extra_models = json.loads(extra_models_json)
        except:
            logger.warning("[REGISTRY] Malformed CLAWBRAIN_LOCAL_MODELS. Using defaults.")
            extra_models = {}

        # Default local models (no prefix needed)
        self.known_no_prefix_models = {
            "gemma4:e4b": "ollama",
            "gemma4:31b": "ollama",
            "qwen2.5:latest": "ollama",
            "llama3:8b": "ollama",
            "deepseek-chat": "deepseek",
        }
        self.known_no_prefix_models.update(extra_models)

    def resolve_provider(self, full_model_name: str) -> Tuple[Optional[str], Optional[ProviderConfig]]:
        """
        Map a model name to its target provider.
        """
        # 1. Explicit Prefix Matching
        if "/" in full_model_name:
            p_name = full_model_name.split("/")[0]
            if p_name in self.providers:
                return p_name, self.providers[p_name]

        # 2. Local Whitelist
        if full_model_name in self.known_no_prefix_models:
            p_name = self.known_no_prefix_models[full_model_name]
            return p_name, self.providers[p_name]

        # 3. No Match -> 501
        return None, None
