# Generated from design/memory_hippocampus.md v1.1
import pytest
import os
import shutil
from pathlib import Path
from src.memory.storage import Hippocampus

# 遵循 Rule 6：所有测试产生的数据必须在 tests/data 下隔离
TEST_DATA_DIR = "/home/nvidia/ClawBrain/tests/data/p7_hippocampus_tmp"

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
    """验证数据落盘并校验返回契约"""
    if os.path.exists(TEST_DATA_DIR): shutil.rmtree(TEST_DATA_DIR)
    hp = Hippocampus(db_dir=TEST_DATA_DIR)
    
    large_data = {"data": "X" * (1024 * 1024)} 
    res = hp.save_trace("large-trace-001", large_data)
    
    visual_audit("Contract: is_blob", "1MB data", True, res["is_blob"])
    assert res["is_blob"] is True
    assert os.path.exists(res["blob_path"])

def test_p7_fts_robust_search():
    """验证全文检索鲁棒性"""
    # 复用同一个测试目录进行不同场景验证
    hp = Hippocampus(db_dir=TEST_DATA_DIR)
    
    fact = "The secret is SILVER-FOX-42"
    hp.save_trace("t-001", {"t": fact}, search_text=fact)
    
    results = hp.search("SILVER-FOX-42")
    visual_audit("Robust Search (Hyphen)", "Query: SILVER-FOX-42", "t-001", results[0] if results else "Not Found")
    
    assert "t-001" in results
