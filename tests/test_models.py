# Generated from design/gateway.md v1.6
from src.models import StandardRequest, Message, Tool
import pytest
import json

def audit_log(input_data, expected, actual):
    print("\n[AUDIT START]")
    print(f"Input: {json.dumps(input_data, indent=2)}")
    print(f"Expected: {expected}")
    print(f"Actual: {actual}")
    print("[AUDIT END]")

def test_standard_request_parsing():
    """验证基本的 OpenAI/Ollama 请求格式能够被正确解析"""
    payload = {
        "model": "ollama/gemma4:e4b",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ],
        "stream": True
    }
    request = StandardRequest(**payload)
    
    audit_log(payload, "ollama/gemma4:e4b", request.model)
    assert request.model == "ollama/gemma4:e4b"
    
    audit_log(payload, 2, len(request.messages))
    assert len(request.messages) == 2

def test_tool_calling_parsing():
    """验证带有工具定义的请求能够被正确解析"""
    payload = {
        "model": "gemma4:31b",
        "messages": [{"role": "user", "content": "Read file"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}
                }
            }
        ]
    }
    request = StandardRequest(**payload)
    
    audit_log(payload, "read_file", request.tools[0].function.name)
    assert request.tools[0].function.name == "read_file"

def test_invalid_request():
    """验证不合规的请求会触发验证错误"""
    payload = {"model": "test-model"} # 缺少 messages
    print(f"\n[AUDIT START] Testing Invalid Input: {payload}")
    try:
        StandardRequest(**payload)
        status = "Success"
    except Exception as e:
        status = f"Failed as expected: {type(e).__name__}"
    
    audit_log(payload, "Failed as expected", status)
    assert "Failed as expected" in status
