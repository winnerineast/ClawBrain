# Generated from design/gateway.md v1.25
from typing import Dict, Any, Tuple

class ProviderConfig:
    def __init__(self, base_url: str, protocol: str):
        self.base_url = base_url
        self.protocol = protocol

class ProviderRegistry:
    """
    智能路由注册表。
    2.2 准则：仅维护 Provider 到真实 URL 的映射。
    """
    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {
            "ollama": ProviderConfig("http://127.0.0.1:11434", "ollama"),
            "lmstudio": ProviderConfig("http://127.0.0.1:1234", "openai"),
            "openai": ProviderConfig("https://api.openai.com", "openai"),
            "deepseek": ProviderConfig("https://api.deepseek.com", "openai"),
            "anthropic": ProviderConfig("https://api.anthropic.com", "openai") # 暂假定 OpenAI 兼容入口
        }

    def resolve_provider(self, full_model_name: str) -> Tuple[str, ProviderConfig]:
        if "/" in full_model_name:
            prefix = full_model_name.split("/")[0]
            if prefix in self.providers:
                return prefix, self.providers[prefix]
        
        return "ollama", self.providers["ollama"]
