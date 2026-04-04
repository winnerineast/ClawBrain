# Generated from design/gateway.md v1.18
import pytest
import json
from src.pipeline import WhitespaceCompressor, SafetyEnforcer, Pipeline
from src.models import StandardRequest, Message
from src.scout import ModelTier

def visual_audit(test_name, input_data, expected, actual):
    match = "YES" if repr(expected) == repr(actual) else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {repr(input_data)[:100]}...")
    print("-" * 60)
    print(f"EXPECTED: {repr(expected)[:50]}...")
    print(f"ACTUAL:   {repr(actual)[:50]}...")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

def test_full_pipeline_precision():
    raw_content = "Task:    Run\n\n\nResult: OK"
    expected_content = "Task: Run\n\nResult: OK" + SafetyEnforcer.TIER2_PATCH
    
    req = StandardRequest(model="test-14b", messages=[Message(role="user", content=raw_content)])
    pipeline = Pipeline()
    optimized_req = pipeline.run(req, ModelTier.TIER_2)
    actual_content = optimized_req.messages[0].content
    
    visual_audit("Pipeline Precision", raw_content, expected_content, actual_content)
    assert actual_content == expected_content
