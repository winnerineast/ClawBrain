# Generated from design/gateway.md v1.32
import re
import httpx
import logging
import time
from typing import Dict, Any, Optional
from enum import Enum

class ModelTier(str, Enum):
    TIER_1 = "TIER_1_EXPERT"
    TIER_2 = "TIER_2_LEGACY"
    TIER_3 = "TIER_3_BASIC"

class ModelScout:
    # Rule 2.2 Fix: Only keep local known model tiers, remove cloud models (e.g., gpt-4) to prevent routing misjudgment
    KNOWN_MODELS = {
        "qwen2.5:latest": ModelTier.TIER_3, # 4.7B confirmed as TIER 3
        "gemma4:e4b": ModelTier.TIER_1,
        "gemma4:31b": ModelTier.TIER_1
    }

    def __init__(self, ollama_base_url: str = "http://127.0.0.1:11434"):
        self.base_url = ollama_base_url
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 600

    async def get_model_tier(self, model_name: str) -> ModelTier:
        # 1. Static rules priority
        if model_name in self.KNOWN_MODELS:
            return self.KNOWN_MODELS[model_name]

        # 2. Cache check
        now = time.time()
        if model_name in self.cache:
            entry = self.cache[model_name]
            if now - entry["timestamp"] < self.cache_ttl:
                return entry["tier"]

        # 3. Dynamic probing (with exception handling)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(f"{self.base_url}/api/show", json={"name": model_name})
                if resp.status_code != 200:
                    return ModelTier.TIER_3
                
                metadata = resp.json()
                tier = self._evaluate(model_name, metadata)
                self.cache[model_name] = {"tier": tier, "timestamp": now}
                return tier
        except Exception:
            return ModelTier.TIER_3

    def _evaluate(self, name: str, meta: Dict[str, Any]) -> ModelTier:
        details = meta.get("details", {})
        param_str = details.get("parameter_size", "0B")
        modelfile = meta.get("modelfile", "").upper()
        
        try:
            params = float(re.findall(r"[-+]?\d*\.\d+|\d+", param_str)[0])
        except Exception:
            params = 0

        has_tools = "TOOLS" in modelfile or "TOOL_CALL" in modelfile
        
        if params >= 20 or (params >= 7 and has_tools):
            return ModelTier.TIER_1
        elif params >= 7:
            return ModelTier.TIER_2
        else:
            return ModelTier.TIER_3
