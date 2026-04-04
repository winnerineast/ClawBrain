# Generated from design/gateway_cloud.md v1.0
import pytest
import json
from src.gateway.translator import DialectTranslator
from src.models import StandardRequest, Message

def visual_audit(test_name, input_desc, expected, actual):
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_desc}")
    print("-" * 60)
    print(f"{'EXPECTED STRUCTURE':<38} | {'ACTUAL STRUCTURE'}")
    print(f"{'-'*38} | {'-'*38}")
    
    # 对比关键字段：Anthropic 的 system 字段
    exp_sys = str(expected.get("system", "Missing"))
    act_sys = str(actual.get("system", "Missing"))
    print(f"{'System Field: ' + exp_sys:<38} | {'System Field: ' + act_sys}")
    
    print("-" * 60)
    print(f"TRANSLATION MATCH: {'YES' if exp_sys == act_sys else 'NO'}")
    print("=" * 80)

def test_p13_anthropic_translation_logic():
    """验证从标准格式向 Anthropic 专属格式的翻译 (剥离 System 消息)"""
    std_req = StandardRequest(
        model="anthropic/claude-3",
        messages=[
            Message(role="system", content="You are Claude."),
            Message(role="user", content="Hello")
        ]
    )
    
    # 执行翻译
    anthropic_payload = DialectTranslator.to_anthropic(std_req)
    
    expected = {"system": "You are Claude."}
    visual_audit("Anthropic Dialect Translation", "Standard with System Msg", expected, anthropic_payload)
    
    # 验证 system 字段已被剥离至顶层
    assert anthropic_payload["system"] == "You are Claude."
    # 验证 messages 数组中不再包含 system
    assert len(anthropic_payload["messages"]) == 1
    assert anthropic_payload["messages"][0]["role"] == "user"

def test_p13_deepseek_openai_compatibility():
    """验证 DeepSeek 使用 OpenAI 方言"""
    std_req = StandardRequest(model="deepseek/chat", messages=[Message(role="user", content="Hi")])
    openai_payload = DialectTranslator.to_openai(std_req)
    
    assert openai_payload["model"] == "chat"
    assert "messages" in openai_payload
