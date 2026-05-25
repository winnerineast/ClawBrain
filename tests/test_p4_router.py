# Generated from design/gateway.md v1.18
import pytest
import respx
import os
import re
import json
from httpx import Response
from fastapi.testclient import TestClient
from src.main import app
from src.memory.storage import clear_chroma_clients

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

def mock_embeddings(request):
    try:
        body = json.loads(request.content)
        inp = body.get("input", "")
        if isinstance(inp, list):
            num_embeddings = len(inp)
        else:
            num_embeddings = 1
    except Exception:
        num_embeddings = 1
    
    embeddings = [[0.1] * 768 for _ in range(num_embeddings)]
    data = [{"embedding": [0.1] * 768} for _ in range(num_embeddings)]
    return Response(200, json={"embeddings": embeddings, "data": data})

@respx.mock
def test_ollama_path_routing(tmp_path):
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)
    
    # Mock embedding calls dynamically based on input batch size
    respx.post(re.compile(r".*/api/embed|.*/v1/embeddings")).mock(side_effect=mock_embeddings)
    
    # Mock upstream Ollama server (match localhost to align with registry config)
    respx.post(re.compile(r"http://(localhost|127.0.0.1):11434/api/chat")).mock(return_value=Response(200, json={"message": {"content": "hi"}}))
    
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"model": "gemma4:e4b", "messages": []})
        visual_audit("Ollama Routing", "/api/chat", 200, response.status_code)
        assert response.status_code == 200

def test_openai_path_routing(tmp_path):
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)
    with TestClient(app) as client:
        # Use an unauthorized model (gpt-4-unauthorized) to verify 501 blocking
        response = client.post("/v1/chat/completions", json={"model": "gpt-4-unauthorized", "messages": []})
        visual_audit("OpenAI Routing", "/v1/chat/completions", 501, response.status_code)
        assert response.status_code == 501
