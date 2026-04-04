# Generated from design/gateway.md v1.7
import time
import httpx
import logging
from enum import Enum
from typing import Dict, Any, Optional

class ModelTier(str, Enum):
    TIER_1 = "TIER_1_NATIVE"    # >= 7B + Tools support
    TIER_2 = "TIER_2_REASONING" # >= 14B + No Native Tools
    TIER_3 = "TIER_3_BASIC"     # < 7B

class ModelScout:
    def __init__(self, ollama_base_url: str = "http://127.0.0.1:11434"):
        self.base_url = ollama_base_url
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 600 # 10 minutes

    async def get_model_tier(self, model_name: str) -> ModelTier:
        # 1. 检查缓存
        now = time.time()
        if model_name in self.cache:
            entry = self.cache[model_name]
            if now - entry["timestamp"] < self.cache_ttl:
                return entry["tier"]

        # 2. 调用 Ollama API 获取元数据
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/show",
                    json={"name": model_name}
                )
                if response.status_code != 200:
                    return ModelTier.TIER_3 # 默认保守策略
                
                metadata = response.json()
                tier = self._classify(metadata)
                
                # 3. 写入缓存
                self.cache[model_name] = {
                    "tier": tier,
                    "timestamp": now
                }
                return tier
        except Exception:
            return ModelTier.TIER_3

    def _classify(self, metadata: Dict[str, Any]) -> ModelTier:
        details = metadata.get("details", {})
        # 尝试从不同的地方获取参数量
        param_size_str = details.get("parameter_size", "0B")
        modelfile = metadata.get("modelfile", "").upper()
        
        # 转换参数量为数值 (例如 '7B' -> 7)
        try:
            params = float(param_size_str.replace("B", "").replace("G", ""))
        except ValueError:
            params = 0

        # 判断准则
        has_tools = "TOOLS" in modelfile or "TOOL_CALL" in modelfile
        
        if params >= 7 and has_tools:
            return ModelTier.TIER_1
        elif params >= 14:
            return ModelTier.TIER_2
        else:
            return ModelTier.TIER_3
