
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
    We verify if internal headers (x-clawbrain-session) and potentially inappropriate auth headers
    are leaked to upstream providers.
    """
    # 1. Setup a mock for the HTTP client used in main.py
    # We want to intercept the outgoing request to see the headers.
    
    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("httpx.AsyncClient.stream") as mock_stream:
        
        # Mock response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Mocked response"}}]}
        mock_resp.is_error = False
        mock_post.return_value = mock_resp
        
        # USE CONTEXT MANAGER to trigger lifespan
        with TestClient(app) as client:
            # Request with sensitive headers
            headers = {
                "x-clawbrain-session": "test-session-123",
                "Authorization": "Bearer sk-leaked-key",
                "X-Custom-Sensitive": "sensitive-value"
            }
            payload = {
                "model": "openai/gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hello"}]
            }
            
            # 2. Trigger the request
            response = client.post("/v1/chat/completions", json=payload, headers=headers)
            
            # 3. Check the mocked outgoing request
            assert mock_post.called
            args, kwargs = mock_post.call_args
            sent_headers = kwargs.get("headers", {})
            
            print("\n[AUDIT] Sent Headers to Upstream:")
            for k, v in sent_headers.items():
                print(f"  {k}: {v}")
                
            # ASSERTIONS: These should NOT be present in sent_headers
            # Note: headers are lowercase in sent_headers usually if passed as dict to httpx, 
            # or it depends on how they are extracted.
            
            leaked_internal = [k for k in sent_headers.keys() if k.lower() == "x-clawbrain-session"]
            leaked_sensitive = [k for k in sent_headers.keys() if k.lower() == "x-custom-sensitive"]
            
            assert not leaked_internal, f"LEAK: x-clawbrain-session forwarded to upstream! ({leaked_internal})"
            assert not leaked_sensitive, f"LEAK: Custom sensitive header forwarded! ({leaked_sensitive})"
            
            print("\n[VERDICT] Reproduction complete. Check assertions above.")

if __name__ == "__main__":
    import asyncio
    pytest.main([__file__])
