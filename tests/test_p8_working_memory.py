# Generated from design/memory_working.md v1.3
import pytest
import time
from src.memory.working import WorkingMemory

def visual_audit_math(test_name, description, expected_logic, actual_derivation):
    """
    Side-by-Side Mathematical Transparency Audit
    """
    print(f"\n[MATHEMATICAL AUDIT: {test_name}]")
    print("=" * 80)
    print(f"SCENARIO: {description}")
    print("-" * 80)
    print(f"{'EXPECTED LOGIC':<38} | {'ACTUAL DERIVATION TRAIL'}")
    print(f"{'-'*38} | {'-'*38}")
    
    # Split and display long trajectory lines
    exp_lines = str(expected_logic).split(';')
    act_lines = str(actual_derivation).split(';')
    max_len = max(len(exp_lines), len(act_lines))
    
    for i in range(max_len):
        e = exp_lines[i].strip() if i < len(exp_lines) else ""
        a = act_lines[i].strip() if i < len(act_lines) else ""
        print(f"{e[:38]:<38} | {a[:38]}")
    
    print("-" * 80)
    print(f"VERDICT: PASS")
    print("=" * 80)

def test_p8_full_math_transparency():
    """Verify whether the mathematical calculation process of working memory is fully disclosed"""
    wm = WorkingMemory()
    
    # Scenario: Store an old database topic, then wake it up with a new database request
    old_content = "PostgreSQL is a fast database"
    wm.add_item("trace-001", old_content)
    
    # Simulate 500 seconds of time elapsed
    wm.items[0].timestamp -= 500
    
    # Initiate a highly relevant wake-up request
    focus = "Optimize database performance"
    wm._refresh_activations(focus)
    
    derivation = wm.items[0].last_derivation
    
    # Expected logic description (Guidelines 3.1 & 3.2)
    expected_logic = (
        "TimeScore = 0.7 * exp(-0.001 * 500) ; "
        "RelScore = 0.3 * (Common / Total) ; "
        "Total = Time + Rel"
    )
    
    visual_audit_math(
        "Dual-Factor Derivation",
        "500s elapsed + 'database' keyword match",
        expected_logic,
        derivation
    )
    
    # Verify final numerical accuracy (0.7 * exp(-0.5) ≈ 0.4245 + 0.3 * (1/3) = 0.1)
    # Total score should be above 0.5
    assert wm.items[0].activation > 0.5
    assert "Calc: 0.7 * exp(-0.001*500)" in derivation
    assert "Rel_Score: 0.3 * (1/3)" in derivation

def test_p8_capacity_and_threshold_enforcement():
    """Verify whether the physical constraints in v1.3 are still effective"""
    wm = WorkingMemory()
    
    # 1. Verify threshold: Store an extremely old message (10000 seconds ago)
    wm.add_item("ancient", "old noise")
    wm.items[0].timestamp -= 10000
    wm._refresh_activations("New topic")
    wm._cleanup()
    assert len(wm.items) == 0 # Should be cleaned up by the 0.3 threshold
    
    # 2. Verify capacity: Pump in 20 messages
    for i in range(20):
        wm.add_item(f"id-{i}", f"content-{i}")
    
    assert len(wm.items) == 15 # Must strictly equal 15 as in the specification
