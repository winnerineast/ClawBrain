# Generated from design/gateway_cloud.md v1.0
from typing import Dict, Any, Tuple

class ProviderConfig:
    def __init__(self, base_url: str, protocol: str):
        self.base_url = base_url
        self.protocol = protocol

class ProviderRegistry:
    """
    提供商路由映射表。
    """
    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {
            "ollama": ProviderConfig("http://127.0.0.1:11434", "ollama"),
            "lmstudio": ProviderConfig("http://127.0.0.1:1234", "openai"),
            "openai": ProviderConfig("https://api.openai.com", "openai"),
            "deepseek": ProviderConfig("https://api.deepseek.com", "openai"),
            "anthropic": ProviderConfig("https://api.anthropic.com", "anthropic")
        }

    def resolve_provider(self, full_model_name: str) -> Tuple[str, ProviderConfig]:
        if "/" in full_model_name:
            prefix = full_model_name.split("/")[0]
            if prefix in self.providers:
                return prefix, self.providers[prefix]
        return "ollama", self.providers["ollama"]
