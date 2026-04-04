# Generated from design/memory_neocortex.md v1.1
import pytest
import os
import shutil
from pathlib import Path
from src.memory.neocortex import Neocortex

TEST_DATA_DIR = "/home/nvidia/ClawBrain/tests/data/p9_neocortex_tmp"

def visual_audit_semantic(test_name, input_desc, canary_facts, summary_text):
    """
    语义提纯打点审计输出：展示事实留存清单
    """
    print(f"\n[SEMANTIC DELTA AUDIT: {test_name}]")
    print("=" * 80)
    print(f"DESCRIPTION: {input_desc}")
    print("-" * 80)
    
    # 分析摘要长度
    print(f"SUMMARY OUTPUT PREVIEW:\n{summary_text[:150]}...\n")
    print(f"{'EXPECTED FACT (CANARY)':<38} | {'ACTUAL PRESERVATION'}")
    print(f"{'-'*38} | {'-'*38}")
    
    all_passed = True
    for fact in canary_facts:
        # 不区分大小写进行判断
        passed = fact.lower() in summary_text.lower()
        if not passed: all_passed = False
        
        status_box = "[ x ]" if passed else "[   ]"
        print(f"{fact[:38]:<38} | {status_box} Retained")
    
    print("-" * 80)
    print(f"SEMANTIC INTEGRITY MATCH: {'YES' if all_passed else 'NO'}")
    print("=" * 80)

@pytest.mark.asyncio
async def test_p9_neocortex_distillation_audit():
    """Phase 9 深度审计：长上下文提取与金丝雀打点验证"""
    if os.path.exists(TEST_DATA_DIR): shutil.rmtree(TEST_DATA_DIR)
    
    nc = Neocortex(db_dir=TEST_DATA_DIR)
    
    # 构造：3条废话 + 1条关键技术决策 (金丝雀)
    traces = [
        {"stimulus": {"messages": [{"role": "user", "content": "Hi, are you there?"}]}, 
         "reaction": {"message": {"content": "Yes, I am here."}}},
        
        {"stimulus": {"messages": [{"role": "user", "content": "We need to set up the database."}]}, 
         "reaction": {"message": {"content": "Okay, which one?"}}},
        
        # --- 核心金丝雀事实 ---
        {"stimulus": {"messages": [{"role": "user", "content": "Let's use PostgreSQL version 15.2 with Tortoise ORM."}]}, 
         "reaction": {"message": {"content": "Understood. I will configure PostgreSQL 15.2 and Tortoise ORM."}}},
         
        {"stimulus": {"messages": [{"role": "user", "content": "Also, what is the weather today?"}]}, 
         "reaction": {"message": {"content": "I am an AI, I don't know the weather."}}}
    ]
    
    canary_facts = ["PostgreSQL", "15.2", "Tortoise"]
    
    # 执行提纯
    summary = await nc.distill("session-audit-01", traces)
    
    # 验证是否提纯成功（未报错）
    assert not summary.startswith("[Error]")
    
    # 执行语义打点审计
    visual_audit_semantic(
        "Knowledge Distillation Pipeline",
        "Distilling 4 rounds of chat to extract core tech decisions",
        canary_facts,
        summary
    )
    
    # 硬核断言：金丝雀事实必须全部存在于摘要中
    for fact in canary_facts:
        assert fact.lower() in summary.lower()
        
    # 验证持久化
    saved_summary = nc.get_summary("session-audit-01")
    assert saved_summary == summary
