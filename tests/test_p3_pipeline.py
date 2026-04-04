# Generated from design/gateway.md v1.7
import pytest
import json
from src.pipeline import WhitespaceCompressor, SafetyEnforcer, Pipeline
from src.models import StandardRequest, Message
from src.scout import ModelTier

def audit_log(input_data, expected, actual):
    print("\n[AUDIT START]")
    print(f"Input: {input_data}")
    print(f"Expected: {expected}")
    print(f"Actual: {actual}")
    print("[AUDIT END]")

def test_whitespace_compression():
    """验证普通文本被压缩，且代码块被保护"""
    input_text = "Hello    world!\n\n\n\n` ` `python\n    def test():\n        pass\n` ` `"
    # 普通文本部分：4个空格应变1个，4个换行应变2个
    # 代码块部分：4个空格缩进必须保留
    
    actual = WhitespaceCompressor.compress(input_text)
    expected_contains_plain = "Hello world!\n\n"
    expected_contains_code = "    def test():"
    
    audit_log(input_text, "Compressed Plain + Protected Code", actual)
    assert expected_contains_plain in actual
    assert expected_contains_code in actual

def test_tier2_enforcement():
    """验证 TIER 2 模型被注入了强制 JSON 补丁"""
    req = StandardRequest(
        model="test-14b",
        messages=[Message(role="user", content="Hello")]
    )
    SafetyEnforcer.apply(req, ModelTier.TIER_2)
    
    audit_log("TIER 2 Request", "Content with Patch", req.messages[0].content)
    assert "[SYSTEM ENFORCEMENT]" in req.messages[0].content

def test_tier1_bypass():
    """验证 TIER 1 模型不被修改内容"""
    original_content = "Hello"
    req = StandardRequest(
        model="gemma4:e4b",
        messages=[Message(role="user", content=original_content)]
    )
    SafetyEnforcer.apply(req, ModelTier.TIER_1)
    
    audit_log("TIER 1 Request", original_content, req.messages[0].content)
    assert req.messages[0].content == original_content
