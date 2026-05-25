# Generated from design/test_sanitization.md v1.0
import pytest
import os
import shutil
import asyncio
import respx
import re
import hashlib
from httpx import Response
from pathlib import Path
from src.memory.router import MemoryRouter
from src.memory.neocortex import Neocortex
from src.memory.storage import clear_chroma_clients, Hippocampus
from src.utils.llm_client import EmbedClient

class DummyEmbedClient(EmbedClient):
    def __init__(self):
        super().__init__("http://dummy", "dummy")
    def _embed(self, texts):
        results = []
        for text in texts:
            vec = [0.0] * 384
            for char in text.lower():
                vec[ord(char) % 384] += 1.0
            mag = sum(v*v for v in vec) ** 0.5
            if mag > 0: vec = [v/mag for v in vec]
            results.append(vec)
        return results
    async def embed(self, texts, **kwargs): return self._embed(texts)
    def embed_sync(self, texts, **kwargs): return self._embed(texts)

def side_by_side_audit(test_name, dimension, input_text, score, verdict):
    print(f"\n[AUDIT] {test_name} | {dimension}")
    print("-" * 70)
    print(f"INPUT:    {input_text[:50]}...")
    print(f"SCORE:    {score}")
    print(f"VERDICT:  {verdict}")
    print("-" * 70)

@pytest.mark.asyncio
@respx.mock
async def test_p65_l6b_precision_filter(tmp_path):
    """Verify L6b filter correctly scores and drops low-value interactions."""
    clear_chroma_clients()
    db_dir = str(tmp_path)
    
    # 1. Force enable cognitive judge for the lifespan of this specific test
    old_judge = os.environ.get("CLAWBRAIN_DISABLE_COGNITIVE_JUDGE")
    os.environ["CLAWBRAIN_DISABLE_COGNITIVE_JUDGE"] = "false"
    
    try:
        # Mock LLM for high-value scoring
        respx.post(re.compile(r".*/api/generate|.*/chat/completions")).mock(side_effect=lambda request: 
            Response(200, json={"response": "0.95", "choices": [{"message": {"content": "0.95"}}]}) 
            if "Use PostgreSQL" in request.content.decode() else 
            Response(200, json={"response": "0.10", "choices": [{"message": {"content": "0.10"}}]})
        )

        router = MemoryRouter(db_dir=db_dir, embed_client=DummyEmbedClient())
        await router.wait_until_ready()
        
        # 2. Ingest High Value (Should be saved)
        tid_high = await router.ingest({"messages": [{"role": "user", "content": "Technical: Use PostgreSQL for production."}]}, sync_distill=True)
        
        # 3. Ingest Low Value (Should be dropped)
        tid_low = await router.ingest({"messages": [{"role": "user", "content": "Hi there, how is the weather?"}]}, sync_distill=True)
        
        high_trace = router.hippo.get_full_payload(tid_high)
        low_trace = router.hippo.get_full_payload(tid_low)
        
        side_by_side_audit("L6b High Value", "Persistence", "Technical: Use PostgreSQL...", "0.95", "SAVED" if high_trace else "DROPPED")
        side_by_side_audit("L6b Low Value", "Persistence", "Hi there, how is...", "0.10", "SAVED" if low_trace else "DROPPED")
        
        assert high_trace is not None
        assert low_trace is None
        
        await router.aclose()
    finally:
        if old_judge is not None:
            os.environ["CLAWBRAIN_DISABLE_COGNITIVE_JUDGE"] = old_judge
        else:
            del os.environ["CLAWBRAIN_DISABLE_COGNITIVE_JUDGE"]

@pytest.mark.asyncio
@respx.mock
async def test_p65_subjective_judge(tmp_path):
    """Verify Cognitive Judge respects the subjective Taste Profile."""
    clear_chroma_clients()
    db_dir = str(tmp_path)
    neo = Neocortex(db_dir=db_dir)
    neo.taste_profile = "User loves Python, hates Java."
    
    # Mock YES only if Python is in the context/query part of the body
    respx.post(re.compile(r".*/api/generate|.*/chat/completions")).mock(side_effect=lambda request: 
        Response(200, json={"response": "YES", "choices": [{"message": {"content": "YES"}}]}) 
        if "Tell me about Python" in request.content.decode() else 
        Response(200, json={"response": "NO", "choices": [{"message": {"content": "NO"}}]})
    )
    
    res_python = await neo.verify_relevance("Tell me about Python", "Python is a great language.")
    res_java = await neo.verify_relevance("Tell me about Java", "Java is very popular.")
    
    side_by_side_audit("Subjective Judge", "Alignment", "Python context", "N/A", "RELEVANT" if res_python else "REJECTED")
    side_by_side_audit("Subjective Judge", "Alignment", "Java context", "N/A", "RELEVANT" if res_java else "REJECTED")
    
    assert res_python is True
    assert res_java is False

@pytest.mark.asyncio
@respx.mock
async def test_p65_tasteguard_distillation(tmp_path):
    """Verify TasteGuard protection in distillation prompt."""
    clear_chroma_clients()
    db_dir = str(tmp_path)
    neo = Neocortex(db_dir=db_dir)
    neo.taste_profile = "TASTEGUARD CORE ANCHOR: We use FastAPI."
    
    # We just want to see if TasteGuard is in the system prompt
    mock_route = respx.post(re.compile(r".*/api/generate|.*/chat/completions")).mock(
        return_value=Response(200, json={"response": "### Technical Decisions\n- Use FastAPI", "choices": [{"message": {"content": "..."}}]})
    )
    
    await neo.distill("sid1", [{"messages": [{"role": "user", "content": "hello"}]}])
    
    last_request = mock_route.calls.last.request
    request_content = last_request.content.decode()
    
    print(f"\n[AUDIT] TasteGuard Visibility")
    print("-" * 70)
    print(f"TASTEGUARD IN PROMPT: {'YES' if 'TASTEGUARD' in request_content else 'NO'}")
    print("-" * 70)
    
    assert "TASTEGUARD" in request_content
    assert "TASTEGUARD CORE ANCHOR: We use FastAPI" in request_content
