# Generated from design/memory_hippocampus.md v1.5
import pytest
import os
import shutil
import hashlib
import json
import sqlite3
from pathlib import Path
from src.memory.storage import Hippocampus

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(PROJECT_ROOT, "tests/data/p7_hippocampus_tmp")

def visual_audit_high_fid(test_name, input_desc, expected_evidence, actual_evidence):
    """
    High-fidelity audit output: displays precise evidence comparison
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
    """Phase 7 Deep Audit: Byte consistency and SHA-256 verification after large file offloading (Fixed Bug 7)"""
    if os.path.exists(TEST_DATA_DIR): shutil.rmtree(TEST_DATA_DIR)
    hp = Hippocampus(db_dir=TEST_DATA_DIR)
    
    # Construct 1MB large file data (> 512KB)
    raw_content = "CANARY_DATA_" + "A" * (1024 * 1024)
    input_payload = {"content": raw_content}
    
    # Calculate Hash of the original JSON string (Expected)
    original_json_str = json.dumps(input_payload)
    expected_hash = get_hash(original_json_str)
    
    # Store in Hippocampus
    res = hp.save_trace("trace-deep-audit", input_payload)
    
    # 1. Verify checksum in the return contract (Bug 7 fix verification)
    system_hash = res.get("checksum")
    
    # 2. Read the generated content from disk and calculate Hash (Physical verification)
    assert res["is_blob"] is True
    with open(res["blob_path"], "r", encoding="utf-8") as f:
        on_disk_content = f.read()
        on_disk_hash = get_hash(on_disk_content)
    
    # 3. Read the stored Hash from the database (Persistence verification)
    db_path = os.path.join(TEST_DATA_DIR, "hippocampus.db")
    conn = sqlite3.connect(db_path)
    db_hash = conn.execute("SELECT checksum FROM traces WHERE trace_id='trace-deep-audit'").fetchone()[0]
    conn.close()
    
    # High-fidelity audit display (Fixed Visual Bug: Ensure that the comparison is of the hash itself)
    visual_audit_high_fid(
        "Storage Byte Integrity & SHA-256",
        "1MB Payload -> Blob Offloading + Hash Check",
        expected_hash, # Pure hash for comparison
        on_disk_hash   # Pure hash for comparison
    )
    
    # Extra print of multi-party evidence for visual review
    print(f"DEBUG EVIDENCE: SYSTEM={system_hash[:8]}... DB={db_hash[:8]}... DISK={on_disk_hash[:8]}...")
    
    # Hardcore assertion: Four-way Hash must be completely consistent
    assert system_hash == expected_hash, "Return metadata checksum mismatch"
    assert db_hash == expected_hash, "Database persistent checksum mismatch"
    assert on_disk_hash == expected_hash, "Physical file content checksum mismatch"

def test_p7_fts_recall_precision_audit():
    """Phase 7 Deep Audit: Full-text search recall precision verification"""
    hp = Hippocampus(db_dir=TEST_DATA_DIR)
    
    # Simulate a high-noise environment: Store 5 useless records
    for i in range(5):
        hp.save_trace(f"noise-{i}", {"text": f"Normal system log line {i}"}, search_text=f"Normal log {i}")
    
    # Insert target canary containing special symbols (hyphens)
    target_fact = "CRITICAL_SECURITY_EVENT: Port 22 opened by user 'admin-root'"
    hp.save_trace("target-99", {"text": target_fact}, search_text=target_fact)
    
    # Perform search: Word with hyphens
    results = hp.search("admin-root")
    
    expected_list = "['target-99']"
    actual_list = str(results)
    
    visual_audit_high_fid(
        "FTS Recall Precision",
        "Search hyphenated word 'admin-root' in 6 logs",
        expected_list,
        actual_list
    )
    
    # Precise verification: Must and can only search for target-99
    assert len(results) == 1
    assert results[0] == "target-99"
