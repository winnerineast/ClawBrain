# Generated from design/gateway.md v1.18
import pytest
import json
from src.models import StandardRequest, Message, Tool

def visual_audit(test_name, input_data, expected, actual):
    match = "YES" if str(expected) == str(actual) else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {json.dumps(input_data)[:100]}...")
    print("-" * 60)
    print(f"{'EXPECTED RESULT':<27} | {'ACTUAL RESULT'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected)[:27]:<27} | {str(actual)[:27]}")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

def test_standard_request_parsing():
    payload = {"model": "ollama/gemma4:e4b", "messages": [{"role": "user", "content": "Hi"}]}
    request = StandardRequest(**payload)
    visual_audit("Model Name Parsing", payload, "ollama/gemma4:e4b", request.model)
    assert request.model == "ollama/gemma4:e4b"

def test_tool_calling_parsing():
    payload = {
        "model": "gemma4:31b",
        "messages": [{"role": "user", "content": "Read file"}],
        "tools": [{"type": "function", "function": {"name": "read_file"}}]
    }
    request = StandardRequest(**payload)
    visual_audit("Tool Name Parsing", payload, "read_file", request.tools[0].function.name)
    assert request.tools[0].function.name == "read_file"
