# Generated from design/config.md v1.0
import pytest
import os
import json
from src.gateway.registry import ProviderRegistry

def visual_audit(test_name, description, expected, actual):
    match = "YES" if str(expected) == str(actual) else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("=" * 70)
    print(f"DESCRIPTION: {description}")
    print("-" * 70)
    print(f"{'EXPECTED':<33} | {'ACTUAL'}")
    print(f"{str(expected)[:33]:<33} | {str(actual)[:33]}")
    print("-" * 70)
    print(f"MATCH: {match}")
    print("=" * 70)

def test_p16_extra_provider_injection():
    """通过环境变量注入新提供商，resolve_provider 应能正确路由"""
    extra = {"myprovider": {"base_url": "https://api.myprovider.com", "protocol": "openai"}}
    os.environ["CLAWBRAIN_EXTRA_PROVIDERS"] = json.dumps(extra)

    registry = ProviderRegistry()
    name, config = registry.resolve_provider("myprovider/gpt-fast")

    visual_audit(
        "Extra Provider Injection",
        "myprovider/gpt-fast should resolve to myprovider",
        "myprovider",
        name
    )
    assert name == "myprovider"
    assert config.base_url == "https://api.myprovider.com"
    assert config.protocol == "openai"

    del os.environ["CLAWBRAIN_EXTRA_PROVIDERS"]

def test_p16_extra_local_models_injection():
    """通过环境变量注入本地模型白名单"""
    extra_models = {"llama3:8b": "ollama", "phi3:mini": "ollama"}
    os.environ["CLAWBRAIN_LOCAL_MODELS"] = json.dumps(extra_models)

    registry = ProviderRegistry()

    for model_id in extra_models:
        name, config = registry.resolve_provider(model_id)
        visual_audit(
            f"Local Model Injection ({model_id})",
            f"{model_id} should route to ollama",
            "ollama",
            name
        )
        assert name == "ollama"

    del os.environ["CLAWBRAIN_LOCAL_MODELS"]

def test_p16_invalid_json_graceful():
    """非法 JSON 不抛异常，注册表仍正常初始化"""
    os.environ["CLAWBRAIN_EXTRA_PROVIDERS"] = "{ this is not valid json !!!"
    os.environ["CLAWBRAIN_LOCAL_MODELS"] = "{ bad }"

    try:
        registry = ProviderRegistry()
        # 原有内置提供商不受影响
        name, config = registry.resolve_provider("ollama/gemma4:e4b")
        visual_audit(
            "Invalid JSON Graceful Fallback",
            "Built-in providers still work after bad env",
            "ollama",
            name
        )
        assert name == "ollama"
    finally:
        del os.environ["CLAWBRAIN_EXTRA_PROVIDERS"]
        del os.environ["CLAWBRAIN_LOCAL_MODELS"]

def test_p16_builtin_providers_intact():
    """内置提供商在无环境变量时保持完整"""
    for key in ["CLAWBRAIN_EXTRA_PROVIDERS", "CLAWBRAIN_LOCAL_MODELS"]:
        os.environ.pop(key, None)

    registry = ProviderRegistry()
    builtin_cases = [
        ("ollama/gemma4:e4b", "ollama"),
        ("anthropic/claude-3", "anthropic"),
        ("google/gemini-pro", "google"),
        ("deepseek/chat", "deepseek"),
    ]
    for model, expected_provider in builtin_cases:
        name, _ = registry.resolve_provider(model)
        visual_audit(f"Builtin Provider ({model})", f"Should route to {expected_provider}", expected_provider, name)
        assert name == expected_provider
