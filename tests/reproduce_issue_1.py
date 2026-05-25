
import pytest
import httpx
import json
from fastapi.testclient import TestClient
from src.main import app
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_header_leak_reproduction():
    """
    Reproduction for Issue #1: Header Forwarding Leaks.
    v1.43: Verifies protocol-specific auth forwarding (x-api-key for anthropic vs Bearer for others).
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Mocked response"}}]}
        mock_resp.is_error = False
        mock_post.return_value = mock_resp
        
        with TestClient(app) as client:
            # --- CASE 1: OpenAI Protocol ---
            headers = {
                "x-clawbrain-session": "test-session-123",
                "Authorization": "Bearer sk-client-key",
                "X-Custom-Sensitive": "sensitive-value"
            }
            payload = {
                "model": "openai/gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hello"}]
            }
            
            client.post("/v1/chat/completions", json=payload, headers=headers)
            sent_headers = mock_post.call_args[1].get("headers", {})
            
            assert "Authorization" in sent_headers
            assert sent_headers["Authorization"] == "Bearer sk-client-key"
            assert "x-clawbrain-session" not in sent_headers
            assert "X-Custom-Sensitive" not in sent_headers
            assert "x-api-key" not in sent_headers

            # --- CASE 2: Anthropic Protocol ---
            mock_post.reset_mock()
            headers = {
                "x-clawbrain-session": "test-session-123",
                "x-api-key": "ant-sk-client-key",
                "Authorization": "Bearer sk-should-be-removed"
            }
            payload = {
                "model": "anthropic/claude-3",
                "messages": [{"role": "user", "content": "Hello"}]
            }
            
            client.post("/v1/chat/completions", json=payload, headers=headers)
            sent_headers = mock_post.call_args[1].get("headers", {})
            
            assert "x-api-key" in sent_headers
            assert sent_headers["x-api-key"] == "ant-sk-client-key"
            assert "Authorization" not in sent_headers # Should be removed for Anthropic
            assert "x-clawbrain-session" not in sent_headers

            # --- CASE 3: Ollama (Internal/Local) ---
            mock_post.reset_mock()
            headers = {
                "Authorization": "Bearer sk-should-be-removed"
            }
            payload = {
                "model": "ollama/llama3",
                "messages": [{"role": "user", "content": "Hello"}]
            }
            
            client.post("/v1/chat/completions", json=payload, headers=headers)
            sent_headers = mock_post.call_args[1].get("headers", {})
            
            assert "Authorization" not in sent_headers # Removed for Ollama by default

if __name__ == "__main__":
    import asyncio
    pytest.main([__file__])
