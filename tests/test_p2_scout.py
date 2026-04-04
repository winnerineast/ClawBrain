# Generated from design/gateway.md v1.7
import pytest
import json
from src.scout import ModelScout, ModelTier

def audit_log(input_data, expected, actual):
    print("\n[AUDIT START]")
    print(f"Input Metadata: {json.dumps(input_data, indent=2)}")
    print(f"Expected Tier: {expected}")
    print(f"Actual Tier: {actual}")
    print("[AUDIT END]")

@pytest.mark.asyncio
async def test_tier_classification():
    scout = ModelScout()
    
    # Case 1: TIER 1 - 7B + Tools
    meta_1 = {"details": {"parameter_size": "7B"}, "modelfile": "TEMPLATE {{ .Tools }}"}
    res_1 = scout._classify(meta_1)
    audit_log(meta_1, ModelTier.TIER_1, res_1)
    assert res_1 == ModelTier.TIER_1

    # Case 2: TIER 2 - 14B, No Tools
    meta_2 = {"details": {"parameter_size": "14B"}, "modelfile": "Simple prompt"}
    res_2 = scout._classify(meta_2)
    audit_log(meta_2, ModelTier.TIER_2, res_2)
    assert res_2 == ModelTier.TIER_2

    # Case 3: TIER 3 - 4B (Small)
    meta_3 = {"details": {"parameter_size": "4B"}, "modelfile": "Small model"}
    res_3 = scout._classify(meta_3)
    audit_log(meta_3, ModelTier.TIER_3, res_3)
    assert res_3 == ModelTier.TIER_3

@pytest.mark.asyncio
async def test_cache_logic():
    scout = ModelScout()
    # 模拟手动注入缓存
    scout.cache["mock-model"] = {"tier": ModelTier.TIER_1, "timestamp": 10000000000} # 永远不过期
    
    # 验证不经过网络直接返回
    res = await scout.get_model_tier("mock-model")
    audit_log("Cache Hit Test", ModelTier.TIER_1, res)
    assert res == ModelTier.TIER_1
