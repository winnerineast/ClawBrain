# Generated from design/gateway.md v1.18
import pytest
import json
from src.scout import ModelScout, ModelTier

def visual_audit(test_name, input_data, expected, actual):
    match = "YES" if expected == actual else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT (Metadata): {json.dumps(input_data)[:100]}...")
    print("-" * 60)
    print(f"{'EXPECTED TIER':<27} | {'ACTUAL TIER'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected):<27} | {str(actual)}")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

@pytest.mark.asyncio
async def test_tier_classification():
    scout = ModelScout()
    # Case: Qwen 2.5 4.7B (Static Registry)
    res = await scout.get_model_tier("qwen2.5:latest")
    visual_audit("Qwen Static Lookup", "qwen2.5:latest", ModelTier.TIER_3, res)
    assert res == ModelTier.TIER_3

    # Case: Gemma 4 e4b (Static Registry)
    res = await scout.get_model_tier("gemma4:e4b")
    visual_audit("Gemma Static Lookup", "gemma4:e4b", ModelTier.TIER_1, res)
    assert res == ModelTier.TIER_1
