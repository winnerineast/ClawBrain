# Generated from design/gateway.md v1.33
import os
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

class ProviderConfig:
    def __init__(self, name: str, base_url: str, protocol: str, api_key: str = ""):
        self.name = name
        self.base_url = base_url
        self.protocol = protocol
        self.api_key = api_key

class ProviderRegistry:
    """
    智能路由注册表。
    2.2 准则修正：强制严谨路由，彻底禁止任何静默回退。
    """
    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {
            "ollama": ProviderConfig("ollama", "http://127.0.0.1:11434", "ollama"),
            "lmstudio": ProviderConfig("lmstudio", "http://127.0.0.1:1234", "openai"),
            "openai": ProviderConfig("openai", "https://api.openai.com", "openai"),
            "deepseek": ProviderConfig("deepseek", "https://api.deepseek.com", "openai"),
            "anthropic": ProviderConfig("anthropic", "https://api.anthropic.com", "anthropic"),
            "google": ProviderConfig("google", "https://generativelanguage.googleapis.com", "google"),
            "mistral": ProviderConfig("mistral", "https://api.mistral.ai", "openai"),
            "xai": ProviderConfig("xai", "https://api.xai.com", "openai"),
            "openrouter": ProviderConfig("openrouter", "https://openrouter.ai/api", "openai")
        }
        
        # 显式定义的无前缀模型路由（白名单）
        # 仅允许已知存在的本地模型直连 Ollama
        self.known_no_prefix_models = {
            "gemma4:e4b": "ollama",
            "gemma4:31b": "ollama",
            "qwen2.5:latest": "ollama"
        }

    def resolve_provider(self, full_model_name: str) -> Tuple[Optional[str], Optional[ProviderConfig]]:
        """
        根据前缀或白名单解析。
        2.2 准则修复：未命中前缀且不在白名单的模型（如 gpt-4）必须返回 None。
        """
        # 1. 检查显式前缀
        if "/" in full_model_name:
            prefix = full_model_name.split("/")[0].lower()
            if prefix in self.providers:
                return prefix, self.providers[prefix]
            # 未知前缀，禁止回退
            return None, None
        
        # 2. 检查无前缀白名单
        if full_model_name in self.known_no_prefix_models:
            p_name = self.known_no_prefix_models[full_model_name]
            return p_name, self.providers[p_name]
        
        # 3. 2.2 准则：彻底移除默认的 ollama 返回逻辑
        return None, None
