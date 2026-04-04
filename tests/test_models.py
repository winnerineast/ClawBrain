# Generated from design/gateway.md v1.6
from src.models import StandardRequest, Message, Tool
import pytest

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
    assert request.model == "ollama/gemma4:e4b"
    assert len(request.messages) == 2
    assert request.stream is True

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
    assert len(request.tools) == 1
    assert request.tools[0].function.name == "read_file"

def test_invalid_request():
    """验证不合规的请求会触发验证错误"""
    with pytest.raises(Exception):
        # 缺少必填字段 messages
        StandardRequest(model="test-model")
