# Generated from design/gateway.md v1.26
import pytest
import json
from src.gateway.translator import DialectTranslator
from src.models import StandardRequest, Message

def visual_audit(test_name, input_desc, expected_evidence, actual_evidence):
    print(f"\n[DIALECT AUDIT: {test_name}]")
    print("=" * 80)
    print(f"DESCRIPTION: {input_desc}")
    print("-" * 80)
    print(f"{'EXPECTED STRUCTURE':<38} | {'ACTUAL STRUCTURE'}")
    print(f"{'-'*38} | {'-'*38}")
    
    # 支持打印字典关键路径对比
    exp_str = json.dumps(expected_evidence, indent=2)
    act_str = json.dumps(actual_evidence, indent=2)
    
    exp_lines = exp_str.split('\n')
    act_lines = act_str.split('\n')
    max_len = max(len(exp_lines), len(act_lines))
    
    for i in range(min(max_len, 10)): # 仅展示前10行
        e = exp_lines[i] if i < len(exp_lines) else ""
        a = act_lines[i] if i < len(act_lines) else ""
        print(f"{e[:38]:<38} | {a[:38]}")
    
    print("-" * 80)
    print(f"DIALECT MATCH: {'YES' if expected_evidence == actual_evidence else 'NO'}")
    print("=" * 80)

def test_p13_google_gemini_translation():
    """验证 Google Gemini 格式翻译：role 映射与 system_instruction"""
    std_req = StandardRequest(
        model="google/gemini-pro",
        messages=[
            Message(role="system", content="Be concise."),
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello")
        ]
    )
    
    payload = DialectTranslator.to_google(std_req)
    
    # 期望结构
    expected = {
        "contents": [
            {"role": "user", "parts": [{"text": "Hi"}]},
            {"role": "model", "parts": [{"text": "Hello"}]}
        ],
        "system_instruction": {"parts": [{"text": "Be concise."}]}
    }
    
    # 抽取关键部分对比 (忽略 generationConfig)
    actual_core = {
        "contents": payload["contents"],
        "system_instruction": payload["system_instruction"]
    }
    
    visual_audit("Google Gemini Dialect", "Map Assistant -> Model, Extract System", expected, actual_core)
    
    assert payload["contents"][1]["role"] == "model"
    assert "system_instruction" in payload

def test_p13_anthropic_role_merge():
    """验证 Anthropic 格式翻译：连续角色合并"""
    std_req = StandardRequest(
        model="anthropic/claude-3",
        messages=[
            Message(role="user", content="Step 1"),
            Message(role="user", content="Step 2")
        ]
    )
    
    payload = DialectTranslator.to_anthropic(std_req)
    
    # 期望：两条 user 消息被合并为一条
    assert len(payload["messages"]) == 1
    assert "Step 1\nStep 2" in payload["messages"][0]["content"]
    
    visual_audit("Anthropic Role Normalization", "Merge redundant User messages", {"count": 1}, {"count": len(payload["messages"])})

def test_p13_openai_prefix_stripping():
    """验证 OpenAI 兼容方言：前缀剥离"""
    std_req = StandardRequest(model="deepseek/deepseek-chat", messages=[Message(role="user", content="Hi")])
    payload = DialectTranslator.to_openai(std_req)
    
    # 期望模型名已剥离前缀
    assert payload["model"] == "deepseek-chat"
    visual_audit("OpenAI Prefix Stripping", "Strip 'deepseek/' from model name", "deepseek-chat", payload["model"])
