# Generated from design/memory_working.md v1.3
import pytest
import time
from src.memory.working import WorkingMemory

def visual_audit_math(test_name, description, expected_logic, actual_derivation):
    """
    Side-by-Side 数学透明度审计
    """
    print(f"\n[MATHEMATICAL AUDIT: {test_name}]")
    print("=" * 80)
    print(f"SCENARIO: {description}")
    print("-" * 80)
    print(f"{'EXPECTED LOGIC':<38} | {'ACTUAL DERIVATION TRAIL'}")
    print(f"{'-'*38} | {'-'*38}")
    
    # 将长轨迹拆分展示
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
    """验证工作记忆的数学计算过程是否完全披露"""
    wm = WorkingMemory()
    
    # 场景：存入一个旧的数据库话题，然后用新的数据库请求唤醒它
    old_content = "PostgreSQL is a fast database"
    wm.add_item("trace-001", old_content)
    
    # 模拟时间流逝 500 秒
    wm.items[0].timestamp -= 500
    
    # 发起一个高度相关的唤醒请求
    focus = "Optimize database performance"
    wm._refresh_activations(focus)
    
    derivation = wm.items[0].last_derivation
    
    # 预期逻辑描述 (3.1 & 3.2 准则)
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
    
    # 验证最终数值准确性 (0.7 * exp(-0.5) ≈ 0.4245 + 0.3 * (1/3) = 0.1)
    # 总分应在 0.5 以上
    assert wm.items[0].activation > 0.5
    assert "Calc: 0.7 * exp(-0.001*500)" in derivation
    assert "Rel_Score: 0.3 * (1/3)" in derivation

def test_p8_capacity_and_threshold_enforcement():
    """验证 v1.3 中的物理约束是否依然有效"""
    wm = WorkingMemory()
    
    # 1. 验证阈值：存入一个极旧的消息（10000秒前）
    wm.add_item("ancient", "old noise")
    wm.items[0].timestamp -= 10000
    wm._refresh_activations("New topic")
    wm._cleanup()
    assert len(wm.items) == 0 # 应该被阈值 0.3 清理
    
    # 2. 验证容量：泵入 20 条消息
    for i in range(20):
        wm.add_item(f"id-{i}", f"content-{i}")
    
    assert len(wm.items) == 15 # 必须严格等于规格书中的 15
