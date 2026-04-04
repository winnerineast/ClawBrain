# Generated from design/memory_hippocampus.md v1.1
import pytest
import os
import shutil
from pathlib import Path
from src.memory.storage import Hippocampus

def visual_audit(test_name, input_summary, expected, actual):
    match = "YES" if expected == actual else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_summary}")
    print("-" * 60)
    print(f"{'EXPECTED':<27} | {'ACTUAL'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected):<27} | {str(actual)}")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

def test_p7_blob_offloading_with_contract():
    """验证 10MB 级数据落盘并校验返回契约"""
    test_dir = "/home/nvidia/ClawBrain/data_test_v1.1"
    if os.path.exists(test_dir): shutil.rmtree(test_dir)
    hp = Hippocampus(db_dir=test_dir)
    
    large_data = {"data": "X" * (1024 * 1024)} 
    res = hp.save_trace("large-trace-001", large_data)
    
    # 验证契约完整性
    visual_audit("Contract: is_blob", "1MB data", True, res["is_blob"])
    visual_audit("Contract: blob_path", "1MB data", "Present", "Present" if res["blob_path"] else "Missing")
    
    assert res["is_blob"] is True
    assert os.path.exists(res["blob_path"])

def test_p7_fts_robust_search():
    """验证带特殊符号的全文检索鲁棒性"""
    test_dir = "/home/nvidia/ClawBrain/data_test_search_v1.1"
    if os.path.exists(test_dir): shutil.rmtree(test_dir)
    hp = Hippocampus(db_dir=test_dir)
    
    # 存入带连字符的 Fact
    fact = "The secret is SILVER-FOX-42"
    hp.save_trace("t-001", {"t": fact}, search_text=fact)
    
    # 执行搜索 (验证修复了 OperationalError)
    results = hp.search("SILVER-FOX-42")
    visual_audit("Robust Search (Hyphen)", "Query: SILVER-FOX-42", "t-001", results[0] if results else "Not Found")
    
    assert "t-001" in results
