# Generated from design/memory_neocortex.md v1.1
import pytest
import os
import shutil
import respx
from httpx import Response
from pathlib import Path
from src.memory.neocortex import Neocortex

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(PROJECT_ROOT, "tests/data/p9_neocortex_tmp")

def visual_audit_semantic(test_name, input_desc, canary_facts, summary_text):
    """
    Semantic Distillation Audit Output: Display fact preservation checklist.
    """
    print(f"\n[SEMANTIC DELTA AUDIT: {test_name}]")
    print("=" * 80)
    print(f"DESCRIPTION: {input_desc}")
    print("-" * 80)
    
    # Preview summary output
    print(f"SUMMARY OUTPUT PREVIEW:\n{summary_text[:150]}...\n")
    print(f"{'EXPECTED FACT (CANARY)':<38} | {'ACTUAL PRESERVATION'}")
    print(f"{'-'*38} | {'-'*38}")
    
    all_passed = True
    for fact in canary_facts:
        passed = fact.lower() in summary_text.lower()
        if not passed: all_passed = False
        
        status_box = "[ x ]" if passed else "[   ]"
        print(f"{fact[:38]:<38} | {status_box} Retained")
    
    print("-" * 80)
    print(f"SEMANTIC INTEGRITY MATCH: {'YES' if all_passed else 'NO'}")
    print("=" * 80)

@pytest.mark.asyncio
@respx.mock
async def test_p9_neocortex_distillation_audit():
    """Phase 9 Depth Audit: Long context extraction and canary fact verification."""
    if os.path.exists(TEST_DATA_DIR): shutil.rmtree(TEST_DATA_DIR)
    
    nc = Neocortex(db_dir=TEST_DATA_DIR)
    
    # Mock Ollama Response containing the canary facts
    mock_summary = "Technical decisions: Use PostgreSQL 15.2 and Tortoise ORM."
    respx.post(f"{nc.distill_url}/api/generate").mock(return_value=Response(200, json={"response": mock_summary}))
    
    # Construct: 3 noise turns + 1 core tech decision (Canary)
    traces = [
        {"stimulus": {"messages": [{"role": "user", "content": "Hi, are you there?"}]}, 
         "reaction": {"message": {"content": "Yes, I am here."}}},
        
        {"stimulus": {"messages": [{"role": "user", "content": "We need to set up the database."}]}, 
         "reaction": {"message": {"content": "Okay, which one?"}}},
        
        # --- Core Canary Fact ---
        {"stimulus": {"messages": [{"role": "user", "content": "Let's use PostgreSQL version 15.2 with Tortoise ORM."}]}, 
         "reaction": {"message": {"content": "Understood. I will configure PostgreSQL 15.2 and Tortoise ORM."}}},
         
        {"stimulus": {"messages": [{"role": "user", "content": "Also, what is the weather today?"}]}, 
         "reaction": {"message": {"content": "I am an AI, I don't know the weather."}}}
    ]
    
    canary_facts = ["PostgreSQL", "15.2", "Tortoise"]
    
    # Execute distillation
    summary = await nc.distill("session-audit-01", traces)
    
    # Verify success (no error prefix)
    assert not summary.startswith("[Error]")
    
    # Perform semantic audit
    visual_audit_semantic(
        "Knowledge Distillation Pipeline",
        "Distilling 4 rounds of chat to extract core tech decisions",
        canary_facts,
        summary
    )
    
    # Hard assertion: Canary facts must be present in the summary
    for fact in canary_facts:
        assert fact.lower() in summary.lower()
        
    # Verify persistence
    saved_summary = nc.get_summary("session-audit-01")
    assert saved_summary == summary
