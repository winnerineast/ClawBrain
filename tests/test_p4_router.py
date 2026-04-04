# Generated from design/gateway.md v1.18
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def visual_audit(test_name, path, expected, actual):
    match = "YES" if expected == actual else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"PATH: {path}")
    print("-" * 60)
    print(f"{'EXPECTED STATUS':<27} | {'ACTUAL STATUS'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected):<27} | {str(actual)}")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

def test_ollama_path_routing():
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"model": "gemma4:e4b", "messages": []})
        visual_audit("Ollama Routing", "/api/chat", 200, response.status_code)
        assert response.status_code == 200

def test_openai_path_routing():
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json={"model": "gpt-4", "messages": []})
        visual_audit("OpenAI Routing", "/v1/chat/completions", 501, response.status_code)
        assert response.status_code == 501
