# Generated from design/memory_working.md v1.1
import pytest
import time
import asyncio
from src.memory.working import WorkingMemory

def visual_audit(test_name, input_summary, time_score, rel_score, total, action):
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_summary}")
    print("-" * 60)
    print(f"{'METRIC':<27} | {'VALUE'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{'Time Score':<27} | {time_score:.4f}")
    print(f"{'Relevance Score':<27} | {rel_score:.4f}")
    print(f"{'Total Activation':<27} | {total:.4f}")
    print("-" * 60)
    print(f"ACTION: {action}")
    print("=" * 60)

def test_p8_temporal_decay():
    """验证时间远离导致的激活值下降"""
    wm = WorkingMemory()
    wm.add_item("t1", "Context A")
    
    initial_act = wm.items[0].activation
    
    # 模拟时间流逝 (修改 timestamp)
    wm.items[0].timestamp -= 1000 
    wm._refresh_activations("Random Topic")
    
    decayed_act = wm.items[0].activation
    visual_audit("Temporal Decay", "1000s elapsed", 0.0, 0.0, decayed_act, "Decay Verified")
    
    assert decayed_act < initial_act

def test_p8_relevance_awakening():
    """验证相关话题对旧记忆的唤醒作用"""
    wm = WorkingMemory()
    # 存入一个旧的关于 PostgreSQL 的记忆
    wm.add_item("t1", "PostgreSQL is a powerful database")
    wm.items[0].timestamp -= 2000 # 设置为较旧
    
    # 第一次更新：无关话题，激活值应该很低
    wm._refresh_activations("How is the weather?")
    low_act = wm.items[0].activation
    
    # 第二次更新：相关话题 "Database performance"
    wm._refresh_activations("Database performance optimization")
    high_act = wm.items[0].activation
    
    visual_audit("Relevance Awakening", "Database -> Database", 0.0, 0.0, high_act, "Awaken Verified")
    
    # 验证相关性导致分值回升
    assert high_act > low_act

def test_p8_noise_eviction():
    """验证无关噪音被自动淘汰"""
    wm = WorkingMemory()
    # 1. 存入一个噪音
    wm.add_item("noise", "xyz abc unrelated")
    # 2. 模拟时间流逝
    wm.items[0].timestamp -= 5000 
    # 3. 注入一个完全无关的新话题
    wm.add_item("new", "completely different topic")
    
    # 检查噪音是否被清理
    trace_ids = [it.trace_id for it in wm.items]
    visual_audit("Noise Eviction", "Unrelated old msg", 0.0, 0.0, 0.0, "Evicted" if "noise" not in trace_ids else "Stayed")
    
    assert "noise" not in trace_ids
