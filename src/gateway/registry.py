# Generated from design/gateway.md v1.22
from typing import Dict, Any, Tuple

class ProviderConfig:
    def __init__(self, base_url: str, protocol: str):
        self.base_url = base_url
        self.protocol = protocol # 'ollama' 或 'openai'

class ProviderRegistry:
    """
    动态提供商注册表。
    负责根据前缀路由到对应的真实后端，而无需硬编码类。
    """
    def __init__(self):
        # 默认配置
        self.providers: Dict[str, ProviderConfig] = {
            "ollama": ProviderConfig(base_url="http://127.0.0.1:11434", protocol="ollama"),
            "lmstudio": ProviderConfig(base_url="http://127.0.0.1:1234", protocol="openai"),
            "openai": ProviderConfig(base_url="https://api.openai.com", protocol="openai"),
            "deepseek": ProviderConfig(base_url="https://api.deepseek.com", protocol="openai")
        }

    def resolve_provider(self, full_model_name: str) -> Tuple[str, ProviderConfig]:
        """
        例如：'lmstudio/llama3' -> ('lmstudio', ProviderConfig)
        默认回退为 ollama。
        """
        if "/" in full_model_name:
            provider_prefix = full_model_name.split("/")[0]
            if provider_prefix in self.providers:
                return provider_prefix, self.providers[provider_prefix]
        
        # 默认路由
        return "ollama", self.providers["ollama"]
