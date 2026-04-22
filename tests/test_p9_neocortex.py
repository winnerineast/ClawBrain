# Generated from design/memory_neocortex.md v2.0
import pytest
import os
import shutil
import respx
import json
from httpx import Response
from pathlib import Path
from src.memory.neocortex import Neocortex
from src.memory.storage import clear_chroma_clients

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(PROJECT_ROOT, "tests/data/p9_neocortex_tmp")

def visual_audit_semantic(test_name, input_desc, canary_facts, thoughts_list):
    """
    Semantic Distillation Audit Output: Display fact preservation checklist for thoughts.
    """
    print(f"\n[SEMANTIC THOUGHT AUDIT: {test_name}]")
    print("=" * 80)
    print(f"DESCRIPTION: {input_desc}")
    print("-" * 80)
    
    all_text = " ".join([t["thought"] for t in thoughts_list])
    
    all_passed = True
    for fact in canary_facts:
        passed = fact.lower() in all_text.lower()
        if not passed: all_passed = False
        
        status_box = "[ x ]" if passed else "[   ]"
        print(f"{fact[:38]:<38} | {status_box} Retained")
    
    print("-" * 80)
    print(f"SEMANTIC INTEGRITY MATCH: {'YES' if all_passed else 'NO'}")
    print("=" * 80)

@pytest.mark.asyncio
@respx.mock
async def test_p9_neocortex_thought_extraction_audit():
    """v0.2.0: Verify Neocortex extracts granular thoughts and maps to root sources."""
    if os.path.exists(TEST_DATA_DIR): shutil.rmtree(TEST_DATA_DIR)
    clear_chroma_clients()
    
    nc = Neocortex(db_dir=TEST_DATA_DIR)
    
    # Mock Ollama Response containing structured JSON thoughts
    mock_thoughts = [
        {"thought": "Use PostgreSQL version 15.2.", "source_traces": ["trace-3"], "confidence": 0.9},
        {"thought": "Implement Tortoise ORM for data mapping.", "source_traces": ["trace-3"], "confidence": 0.8}
    ]
    respx.post(f"{nc.distill_url}/api/generate").mock(return_value=Response(200, json={"response": json.dumps(mock_thoughts)}))
    
    traces = [
        {"trace_id": "trace-1", "payload": {"messages": [{"role": "user", "content": "Hi"}]}},
        {"trace_id": "trace-3", "payload": {"messages": [{"role": "user", "content": "Let's use PostgreSQL version 15.2 with Tortoise ORM."}]}}
    ]
    
    canary_facts = ["PostgreSQL", "15.2", "Tortoise"]
    
    # Execute distillation
    result_msg = await nc.distill("session-audit-01", traces)
    assert "extracted 2 thoughts" in result_msg
    
    # Verify thoughts in storage
    thoughts = nc.hippo.search_thoughts("database", "session-audit-01")
    assert len(thoughts) >= 2
    
    # Perform semantic audit
    visual_audit_semantic(
        "Thought-Retriever Pipeline",
        "Extracting granular thoughts with Root Source Mapping",
        canary_facts,
        thoughts
    )
    
    # Hard assertion: Canary facts must be present in the thoughts
    all_thoughts_text = " ".join([t["thought"] for t in thoughts]).lower()
    for fact in canary_facts:
        assert fact.lower() in all_thoughts_text
        
    # Verify Root Source Mapping
    assert "trace-3" in thoughts[0]["source_traces"]
