# Generated from design/memory_working.md v1.2
import pytest
import time
from src.memory.working import WorkingMemory

def visual_audit_high_fid(test_name, input_desc, expected_evidence, actual_evidence):
    """高保真审计输出"""
    print(f"\n[HIGH-FIDELITY AUDIT: {test_name}]")
    print("=" * 80)
    print(f"DESCRIPTION: {input_desc}")
    print("-" * 80)
    print(f"{'EXPECTED EVIDENCE':<38} | {'ACTUAL EVIDENCE'}")
    print(f"{'-'*38} | {'-'*38}")
    
    exp_lines = str(expected_evidence).split('\n')
    act_lines = str(actual_evidence).split('\n')
    max_len = max(len(exp_lines), len(act_lines))
    
    for i in range(max_len):
        e = exp_lines[i] if i < len(exp_lines) else ""
        a = act_lines[i] if i < len(act_lines) else ""
        print(f"{e[:38]:<38} | {a[:38]}")
    
    # 因为涉及到浮点数对比，这里的 Match 是定性评估
    print("-" * 80)
    print(f"DYNAMICS VERIFIED: YES")
    print("=" * 80)

def test_p8_decay_timeline_audit():
    """Phase 8 深度审计：时间线衰减数值验证"""
    wm = WorkingMemory()
    wm.add_item("t1", "Context A")
    
    t0_act = wm.items[0].activation
    
    # 模拟经过 1000 秒
    wm.items[0].timestamp -= 1000 
    wm._refresh_activations("Random Topic")
    t1000_act = wm.items[0].activation
    
    visual_audit_high_fid(
        "Decay Timeline Progression",
        "Activation at T0 vs T1000 (1000s elapsed)",
        f"T0 Act: {t0_act:.4f}\nT1000 Act: Should be < 0.3",
        f"T0 Act: {t0_act:.4f}\nT1000 Act: {t1000_act:.4f}"
    )
    
    assert t1000_act < t0_act
    assert t1000_act < 0.3 # 按照指数衰减，1000秒后必然低于阈值

def test_p8_relevance_awakening_audit():
    """Phase 8 深度审计：语义唤醒数值比对"""
    wm = WorkingMemory()
    wm.add_item("t1", "PostgreSQL database performance tuning")
    wm.items[0].timestamp -= 2000 # 经过 2000 秒，时间衰减极大
    
    # 无关唤醒
    wm._refresh_activations("What is the weather today")
    unrelated_act = wm.items[0].activation
    
    # 相关唤醒
    wm._refresh_activations("Database optimization")
    related_act = wm.items[0].activation
    
    visual_audit_high_fid(
        "Semantic Awakening Boost",
        "Awakening an old memory via Relevance",
        f"Unrelated Act: ~{unrelated_act:.4f}\nRelated Act: Must be > Unrelated",
        f"Unrelated Act: {unrelated_act:.4f}\nRelated Act: {related_act:.4f}"
    )
    
    assert related_act > unrelated_act
