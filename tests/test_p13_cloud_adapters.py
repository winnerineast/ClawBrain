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
    
    # Print comparison rows
    for key in expected:
        exp_val = str(expected[key])
        act_val = str(actual.get(key, "MISSING"))
        print(f"{key + ': ' + exp_val:<38} | {key + ': ' + act_val}")
    
    print("-" * 60)
    print(f"VERDICT: {'PASS' if all(str(actual.get(k)) == str(v) for k,v in expected.items()) else 'FAIL'}")
    print("=" * 80)

def test_p13_anthropic_role_normalization():
    """Verify: Whether consecutive User messages are merged (compliant with Anthropic specs)"""
    std_req = StandardRequest(
        model="anthropic/claude-3",
        messages=[
            Message(role="user", content="Hello,"),
            Message(role="user", content="how are you?")
        ]
    )
    payload = DialectTranslator.to_anthropic(std_req)
    
    # Expected: messages length should be 1, and content should be merged
    expected = {"msg_count": 1, "first_role": "user"}
    actual = {"msg_count": len(payload["messages"]), "first_role": payload["messages"][0]["role"]}
    
    visual_audit("Role Normalization", "Merge double User messages", expected, actual)
    assert actual["msg_count"] == 1
    assert "how are you?" in payload["messages"][0]["content"]

def test_p13_anthropic_mandatory_fields():
    """Verify: Whether max_tokens is auto-filled"""
    std_req = StandardRequest(model="anthropic/claude-3", messages=[Message(role="user", content="Hi")])
    # Original request does not specify max_tokens
    payload = DialectTranslator.to_anthropic(std_req)
    
    expected = {"max_tokens": 4096}
    visual_audit("Mandatory Fields", "Auto-fill max_tokens", expected, payload)
    assert payload["max_tokens"] == 4096

def test_p13_anthropic_system_mapping():
    """Verify: Whether System messages are correctly mapped to the top level"""
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
