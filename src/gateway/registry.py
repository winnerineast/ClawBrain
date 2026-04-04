# Generated from design/gateway.md v1.26
from typing import Dict, Any, Tuple

class ProviderConfig:
    def __init__(self, base_url: str, protocol: str):
        self.base_url = base_url
        self.protocol = protocol

class ProviderRegistry:
    """
    智能路由注册表。
    2.2 准则：维护全量 Provider 到真实 URL 与协议的映射。
    """
    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {
            "ollama": ProviderConfig("http://127.0.0.1:11434", "ollama"),
            "lmstudio": ProviderConfig("http://127.0.0.1:1234", "openai"),
            "openai": ProviderConfig("https://api.openai.com", "openai"),
            "deepseek": ProviderConfig("https://api.deepseek.com", "openai"),
            "anthropic": ProviderConfig("https://api.anthropic.com", "anthropic"),
            "google": ProviderConfig("https://generativelanguage.googleapis.com", "google"),
            "mistral": ProviderConfig("https://api.mistral.ai", "openai"),
            "xai": ProviderConfig("https://api.xai.com", "openai"),
            "openrouter": ProviderConfig("https://openrouter.ai/api", "openai"),
            "together": ProviderConfig("https://api.together.xyz", "openai"),
            "vllm": ProviderConfig("http://127.0.0.1:8000", "openai"),
            "sglang": ProviderConfig("http://127.0.0.1:30000", "openai")
        }

    def resolve_provider(self, full_model_name: str) -> Tuple[str, ProviderConfig]:
        """
        根据模型前缀解析 Provider。
        例如：'google/gemini-pro' -> ('google', ProviderConfig)
        """
        if "/" in full_model_name:
            prefix = full_model_name.split("/")[0].lower()
            if prefix in self.providers:
                return prefix, self.providers[prefix]
        
        # 默认路由
        return "ollama", self.providers["ollama"]
