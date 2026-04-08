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
    
    # Support printing comparison of key dictionary paths
    exp_str = json.dumps(expected_evidence, indent=2)
    act_str = json.dumps(actual_evidence, indent=2)
    
    exp_lines = exp_str.split('\n')
    act_lines = act_str.split('\n')
    max_len = max(len(exp_lines), len(act_lines))
    
    for i in range(min(max_len, 10)): # Only display the first 10 lines
        e = exp_lines[i] if i < len(exp_lines) else ""
        a = act_lines[i] if i < len(act_lines) else ""
        print(f"{e[:38]:<38} | {a[:38]}")
    
    print("-" * 80)
    print(f"DIALECT MATCH: {'YES' if expected_evidence == actual_evidence else 'NO'}")
    print("=" * 80)

def test_p13_google_gemini_translation():
    """Verify Google Gemini format translation: role mapping and system_instruction"""
    std_req = StandardRequest(
        model="google/gemini-pro",
        messages=[
            Message(role="system", content="Be concise."),
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello")
        ]
    )
    
    payload = DialectTranslator.to_google(std_req)
    
    # Expected structure
    expected = {
        "contents": [
            {"role": "user", "parts": [{"text": "Hi"}]},
            {"role": "model", "parts": [{"text": "Hello"}]}
        ],
        "system_instruction": {"parts": [{"text": "Be concise."}]}
    }
    
    # Extract key parts for comparison (ignore generationConfig)
    actual_core = {
        "contents": payload["contents"],
        "system_instruction": payload["system_instruction"]
    }
    
    visual_audit("Google Gemini Dialect", "Map Assistant -> Model, Extract System", expected, actual_core)
    
    assert payload["contents"][1]["role"] == "model"
    assert "system_instruction" in payload

def test_p13_anthropic_role_merge():
    """Verify Anthropic format translation: consecutive role merging"""
    std_req = StandardRequest(
        model="anthropic/claude-3",
        messages=[
            Message(role="user", content="Step 1"),
            Message(role="user", content="Step 2")
        ]
    )
    
    payload = DialectTranslator.to_anthropic(std_req)
    
    # Expected: Two user messages are merged into one
    assert len(payload["messages"]) == 1
    assert "Step 1\nStep 2" in payload["messages"][0]["content"]
    
    visual_audit("Anthropic Role Normalization", "Merge redundant User messages", {"count": 1}, {"count": len(payload["messages"])})

def test_p13_openai_prefix_stripping():
    """Verify OpenAI-compatible dialects: prefix stripping"""
    std_req = StandardRequest(model="deepseek/deepseek-chat", messages=[Message(role="user", content="Hi")])
    payload = DialectTranslator.to_openai(std_req)
    
    # Expected model name has the prefix stripped
    assert payload["model"] == "deepseek-chat"
    visual_audit("OpenAI Prefix Stripping", "Strip 'deepseek/' from model name", "deepseek-chat", payload["model"])
