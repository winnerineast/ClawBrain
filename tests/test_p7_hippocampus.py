# Generated from design/memory_hippocampus.md v1.5
import pytest
import os
import shutil
import hashlib
import json
import sqlite3
from pathlib import Path
from src.memory.storage import Hippocampus

TEST_DATA_DIR = "/home/nvidia/ClawBrain/tests/data/p7_hippocampus_tmp"

def visual_audit_high_fid(test_name, input_desc, expected_evidence, actual_evidence):
    """
    高保真审计输出：展示精确的证据对比
    """
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
    
    print("-" * 80)
    print(f"INTEGRITY MATCH: {'YES' if str(expected_evidence) == str(actual_evidence) else 'NO'}")
    print("=" * 80)

def get_hash(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def test_p7_storage_integrity_audit():
    """Phase 7 深度审计：大文件分流后的字节一致性与 SHA-256 校验 (Fixed Bug 7)"""
    if os.path.exists(TEST_DATA_DIR): shutil.rmtree(TEST_DATA_DIR)
    hp = Hippocampus(db_dir=TEST_DATA_DIR)
    
    # 构造 1MB 的大文件数据 (> 512KB)
    raw_content = "CANARY_DATA_" + "A" * (1024 * 1024)
    input_payload = {"content": raw_content}
    
    # 计算原始 JSON 字符串的 Hash (预期)
    original_json_str = json.dumps(input_payload)
    expected_hash = get_hash(original_json_str)
    
    # 存入海马体
    res = hp.save_trace("trace-deep-audit", input_payload)
    
    # 1. 验证返回契约中的 checksum (Bug 7 修复验证)
    system_hash = res.get("checksum")
    
    # 2. 从磁盘读取产生的内容并计算 Hash (物理确证)
    assert res["is_blob"] is True
    with open(res["blob_path"], "r", encoding="utf-8") as f:
        on_disk_content = f.read()
        on_disk_hash = get_hash(on_disk_content)
    
    # 3. 从数据库中读取存证 Hash (持久化确证)
    db_path = os.path.join(TEST_DATA_DIR, "hippocampus.db")
    conn = sqlite3.connect(db_path)
    db_hash = conn.execute("SELECT checksum FROM traces WHERE trace_id='trace-deep-audit'").fetchone()[0]
    conn.close()
    
    # 高保真审计展示 (Fixed Visual Bug: 确保比较的是哈希本身)
    visual_audit_high_fid(
        "Storage Byte Integrity & SHA-256",
        "1MB Payload -> Blob Offloading + Hash Check",
        expected_hash, # 纯哈希用于比较
        on_disk_hash   # 纯哈希用于比较
    )
    
    # 额外打印多方证据用于肉眼复核
    print(f"DEBUG EVIDENCE: SYSTEM={system_hash[:8]}... DB={db_hash[:8]}... DISK={on_disk_hash[:8]}...")
    
    # 硬核断言：四方 Hash 必须完全一致
    assert system_hash == expected_hash, "Return metadata checksum mismatch"
    assert db_hash == expected_hash, "Database persistent checksum mismatch"
    assert on_disk_hash == expected_hash, "Physical file content checksum mismatch"

def test_p7_fts_recall_precision_audit():
    """Phase 7 深度审计：全文检索的召回精度验证"""
    hp = Hippocampus(db_dir=TEST_DATA_DIR)
    
    # 模拟高噪音环境：存入 5 条无用记录
    for i in range(5):
        hp.save_trace(f"noise-{i}", {"text": f"Normal system log line {i}"}, search_text=f"Normal log {i}")
    
    # 插入包含特殊符号（连字符）的目标金丝雀
    target_fact = "CRITICAL_SECURITY_EVENT: Port 22 opened by user 'admin-root'"
    hp.save_trace("target-99", {"text": target_fact}, search_text=target_fact)
    
    # 执行搜索：带有连字符的词
    results = hp.search("admin-root")
    
    expected_list = "['target-99']"
    actual_list = str(results)
    
    visual_audit_high_fid(
        "FTS Recall Precision",
        "Search hyphenated word 'admin-root' in 6 logs",
        expected_list,
        actual_list
    )
    
    # 精确验证：必须且仅能搜到 target-99
    assert len(results) == 1
    assert results[0] == "target-99"
