# Generated from design/config.md v1.0
import os
import json
import logging
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

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
    智能路由注册表。支持环境变量热扩展。
    """
    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {
            "ollama":      ProviderConfig("ollama",      "http://127.0.0.1:11434",                    "ollama"),
            "lmstudio":    ProviderConfig("lmstudio",    "http://127.0.0.1:1234",                     "openai"),
            "openai":      ProviderConfig("openai",      "https://api.openai.com",                    "openai"),
            "deepseek":    ProviderConfig("deepseek",    "https://api.deepseek.com",                  "openai"),
            "anthropic":   ProviderConfig("anthropic",   "https://api.anthropic.com",                 "anthropic"),
            "google":      ProviderConfig("google",      "https://generativelanguage.googleapis.com", "google"),
            "mistral":     ProviderConfig("mistral",     "https://api.mistral.ai",                    "openai"),
            "xai":         ProviderConfig("xai",         "https://api.xai.com",                       "openai"),
            "openrouter":  ProviderConfig("openrouter",  "https://openrouter.ai/api",                 "openai"),
            "together":    ProviderConfig("together",    "https://api.together.xyz",                  "openai"),
        }

        self.known_no_prefix_models = {
            "gemma4:e4b":      "ollama",
            "gemma4:31b":      "ollama",
            "qwen2.5:latest":  "ollama",
        }

        # P16: 环境变量扩展提供商
        extra_providers_json = os.getenv("CLAWBRAIN_EXTRA_PROVIDERS")
        if extra_providers_json:
            try:
                extras = json.loads(extra_providers_json)
                for name, cfg in extras.items():
                    self.providers[name] = ProviderConfig(
                        name,
                        cfg["base_url"],
                        cfg.get("protocol", "openai")
                    )
                logger.info(f"[REGISTRY] Loaded {len(extras)} extra provider(s) from env.")
            except Exception as e:
                logger.warning(f"[REGISTRY] CLAWBRAIN_EXTRA_PROVIDERS parse failed: {e}")

        # P16: 环境变量扩展本地模型白名单
        extra_models_json = os.getenv("CLAWBRAIN_LOCAL_MODELS")
        if extra_models_json:
            try:
                extra_models = json.loads(extra_models_json)
                self.known_no_prefix_models.update(extra_models)
                logger.info(f"[REGISTRY] Loaded {len(extra_models)} extra local model(s) from env.")
            except Exception as e:
                logger.warning(f"[REGISTRY] CLAWBRAIN_LOCAL_MODELS parse failed: {e}")

    def resolve_provider(self, full_model_name: str) -> Tuple[Optional[str], Optional[ProviderConfig]]:
        # 1. 显式前缀匹配
        if "/" in full_model_name:
            prefix = full_model_name.split("/")[0].lower()
            if prefix in self.providers:
                return prefix, self.providers[prefix]
            return None, None

        # 2. 本地白名单
        if full_model_name in self.known_no_prefix_models:
            p_name = self.known_no_prefix_models[full_model_name]
            return p_name, self.providers[p_name]

        # 3. 无匹配 → 501
        return None, None
