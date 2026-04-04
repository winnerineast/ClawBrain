# Generated from design/gateway_cloud.md v1.1
import pytest
import json
from src.gateway.translator import DialectTranslator
from src.models import StandardRequest, Message

def visual_audit(test_name, input_desc, expected, actual):
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"DESCRIPTION: {input_desc}")
    print("-" * 60)
    print(f"{'EXPECTED ATTRIBUTE':<38} | {'ACTUAL ATTRIBUTE'}")
    print(f"{'-'*38} | {'-'*38}")
    
    # 打印对比行
    for key in expected:
        exp_val = str(expected[key])
        act_val = str(actual.get(key, "MISSING"))
        print(f"{key + ': ' + exp_val:<38} | {key + ': ' + act_val}")
    
    print("-" * 60)
    print(f"VERDICT: {'PASS' if all(str(actual.get(k)) == str(v) for k,v in expected.items()) else 'FAIL'}")
    print("=" * 80)

def test_p13_anthropic_role_normalization():
    """验证：连续两条 User 消息是否被合并（符合 Anthropic 规格）"""
    std_req = StandardRequest(
        model="anthropic/claude-3",
        messages=[
            Message(role="user", content="Hello,"),
            Message(role="user", content="how are you?")
        ]
    )
    payload = DialectTranslator.to_anthropic(std_req)
    
    # 预期：messages 长度应为 1，且内容合并
    expected = {"msg_count": 1, "first_role": "user"}
    actual = {"msg_count": len(payload["messages"]), "first_role": payload["messages"][0]["role"]}
    
    visual_audit("Role Normalization", "Merge double User messages", expected, actual)
    assert actual["msg_count"] == 1
    assert "how are you?" in payload["messages"][0]["content"]

def test_p13_anthropic_mandatory_fields():
    """验证：max_tokens 是否被自动补全"""
    std_req = StandardRequest(model="anthropic/claude-3", messages=[Message(role="user", content="Hi")])
    # 原始请求未指定 max_tokens
    payload = DialectTranslator.to_anthropic(std_req)
    
    expected = {"max_tokens": 4096}
    visual_audit("Mandatory Fields", "Auto-fill max_tokens", expected, payload)
    assert payload["max_tokens"] == 4096

def test_p13_anthropic_system_mapping():
    """验证：System 消息正确映射到顶层"""
    std_req = StandardRequest(
        model="anthropic/claude-3",
        messages=[
            Message(role="system", content="Admin Mode"),
            Message(role="user", content="Hi")
        ]
    )
    payload = DialectTranslator.to_anthropic(std_req)
    
    expected = {"system": "Admin Mode"}
    visual_audit("System Field Mapping", "System msg to Top-level", expected, payload)
    assert payload["system"] == "Admin Mode"
    assert len(payload["messages"]) == 1
