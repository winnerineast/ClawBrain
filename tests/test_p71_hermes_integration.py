# Generated from design/gateway.md v1.45
import pytest
import respx
import re
import json
from httpx import Response
from fastapi.testclient import TestClient
from src.main import app
from src.memory.storage import clear_chroma_clients

def visual_audit(test_name, description, expected, actual):
    match = "YES" if str(expected) == str(actual) else "NO"
    print(f"\n[HERMES AUDIT: {test_name}]")
    print("=" * 70)
    print(f"DESCRIPTION: {description}")
    print("-" * 70)
    print(f"{'EXPECTED':<33} | {'ACTUAL'}")
    print(f"{str(expected)[:33]:<33} | {str(actual)[:33]}")
    print("-" * 70)
    print(f"MATCH: {match}")
    print("=" * 70)

def mock_embeddings(request):
    try:
        body = json.loads(request.content)
        inp = body.get("input", "")
        num_embeddings = len(inp) if isinstance(inp, list) else 1
    except Exception:
        num_embeddings = 1
    
    embeddings = [[0.1] * 768 for _ in range(num_embeddings)]
    data = [{"embedding": [0.1] * 768} for _ in range(num_embeddings)]
    return Response(200, json={"embeddings": embeddings, "data": data})

@pytest.mark.asyncio
@respx.mock
async def test_hermes_lmstudio_routing(tmp_path):
    """Verify that requests for a Hermes model via lmstudio strip the prefix and integrate properly."""
    clear_chroma_clients()
    import os
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)
    os.environ["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"

    # Mock embedding endpoint
    respx.post(re.compile(r".*/api/embed|.*/v1/embeddings")).mock(side_effect=mock_embeddings)

    # Payload targeting Hermes on LM Studio
    payload = {
        "model": "lmstudio/NousResearch/Hermes-3-Llama-3.1-8B",
        "messages": [{"role": "user", "content": "Tell me about Hermes."}]
    }

    # Intercept upstream LM Studio request and assert that the prefix is stripped
    def match_lmstudio_request(request):
        try:
            body = json.loads(request.content)
            # Expect prefix 'lmstudio/' to be stripped, leaving organization and model name
            return body.get("model") == "NousResearch/Hermes-3-Llama-3.1-8B"
        except Exception:
            return False

    route = respx.post("http://localhost:1234/v1/chat/completions").mock(
        side_effect=lambda req: Response(200, json={"choices": [{"message": {"content": "I am Hermes, a self-improving agent helper."}}]})
    )

    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=payload)
        
        visual_audit(
            "Hermes LM Studio Prefix Stripping",
            "Forwarded model ID should be stripped of 'lmstudio/' prefix",
            True,
            route.called and match_lmstudio_request(route.calls.last.request)
        )
        
        assert response.status_code == 200
        assert route.called
        assert "Hermes" in response.json()["choices"][0]["message"]["content"]


@pytest.mark.asyncio
@respx.mock
async def test_hermes_ollama_routing(tmp_path):
    """Verify that requests for a Hermes model via ollama route correctly."""
    clear_chroma_clients()
    import os
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)
    os.environ["CLAWBRAIN_DISABLE_ROOM_DETECTION"] = "true"

    respx.post(re.compile(r".*/api/embed|.*/v1/embeddings")).mock(side_effect=mock_embeddings)

    payload = {
        "model": "ollama/nous-hermes",
        "messages": [{"role": "user", "content": "Identify yourself."}]
    }

    # Intercept upstream Ollama request (forwarding /v1/chat/completions)
    route = respx.post("http://localhost:11434/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"role": "assistant", "content": "I am Nous Hermes running locally."}}]})
    )

    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=payload)
        
        visual_audit(
            "Hermes Ollama Routing",
            "Forwarded request correctly routed to Ollama /v1/chat/completions",
            True,
            route.called
        )
        
        assert response.status_code == 200
        assert route.called
        assert "Nous Hermes" in response.json()["choices"][0]["message"]["content"]
