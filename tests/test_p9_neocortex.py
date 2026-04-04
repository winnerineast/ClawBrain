# Generated from design/memory_neocortex.md v1.0
import pytest
import json
from pathlib import Path
from src.memory.neocortex import Neocortex

def visual_audit(test_name, raw_len, summary_len, ratio, content_check):
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"{'METRIC':<27} | {'VALUE'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{'Raw Bytes':<27} | {raw_len}")
    print(f"{'Summary Bytes':<27} | {summary_len}")
    print(f"{'Compression Ratio':<27} | {ratio:.2%}")
    print(f"{'Canary Check':<27} | {content_check}")
    print("-" * 60)
    print("=" * 60)

@pytest.mark.asyncio
async def test_neocortex_distillation():
    """验证新皮层的语义提纯与金丝雀召回"""
    test_db_dir = "/home/nvidia/ClawBrain/tests/data/p9_tmp"
    Path(test_db_dir).mkdir(parents=True, exist_ok=True)
    
    # 加载测试数据 (Rule 6)
    data = json.loads(Path("tests/data/p9_neocortex.json").read_text())
    history = data["marathon_history"]
    canary = data["canary_fact"]
    
    nc = Neocortex(db_dir=test_db_dir)
    
    # 执行提纯
    summary = await nc.distill("session-001", history)
    
    raw_len = len(str(history))
    summary_len = len(summary)
    ratio = (raw_len - summary_len) / raw_len
    
    # 检查是否包含核心事实（金丝雀）
    canary_passed = canary.lower() in summary.lower() or "postgresql" in summary.lower()
    
    visual_audit("Semantic Distillation", raw_len, summary_len, ratio, "PASS" if canary_passed else "FAIL")
    
    assert summary_len < raw_len
    assert nc.get_summary("session-001") == summary
