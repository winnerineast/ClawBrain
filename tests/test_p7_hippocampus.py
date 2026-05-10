# Generated from design/memory_hippocampus.md v1.11 / Issue #48
import pytest
import os
import shutil
import hashlib
import json
import sqlite3
from pathlib import Path
from src.memory.storage import Hippocampus, clear_chroma_clients
from src.utils.llm_client import EmbedClient

class DummyEmbedClient(EmbedClient):
    def __init__(self):
        super().__init__("http://dummy", "dummy")
    def _embed(self, texts):
        results = []
        for text in texts:
            vec = [0.0] * 384
            for char in text.lower():
                vec[ord(char) % 384] += 1.0
            mag = sum(v*v for v in vec) ** 0.5
            if mag > 0: vec = [v/mag for v in vec]
            results.append(vec)
        return results
    async def embed(self, texts, **kwargs): return self._embed(texts)
    def embed_sync(self, texts, **kwargs): return self._embed(texts)

def visual_audit_high_fid(test_name, input_desc, expected_evidence, actual_evidence):
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

def test_p7_storage_integrity_audit(tmp_path):
    """Phase 7 Deep Audit: Byte consistency and SHA-256 verification after large file offloading (Fixed Bug 7)"""
    clear_chroma_clients()
    hp = Hippocampus(db_dir=str(tmp_path), embed_client=DummyEmbedClient())
    
    # Construct 1MB large file data (> 512KB)
    raw_content = "CANARY_DATA_" + "A" * (1024 * 1024)
    input_payload = {"content": raw_content}
    
    # Calculate Hash of the original JSON string (Expected)
    original_json_str = json.dumps(input_payload)
    expected_hash = get_hash(original_json_str)
    
    # Store in Hippocampus
    res = hp.save_trace("trace-deep-audit", input_payload)
    
    # 1. Verify checksum in the return contract
    system_hash = res.get("checksum")
    
    # 2. Read the generated content from disk and calculate Hash
    assert res["is_blob"] is True
    with open(res["blob_path"], "r", encoding="utf-8") as f:
        on_disk_content = f.read()
        on_disk_hash = get_hash(on_disk_content)
    
    # 3. Read the stored Hash from ChromaDB
    chroma_res = hp.traces_col.get(ids=["trace-deep-audit"])
    db_hash = chroma_res["metadatas"][0]["checksum"]
    
    # High-fidelity audit display
    visual_audit_high_fid(
        "Storage Byte Integrity & SHA-256",
        "1MB Payload -> Blob Offloading + Hash Check",
        expected_hash,
        on_disk_hash
    )
    
    assert system_hash == expected_hash
    assert db_hash == expected_hash
    assert on_disk_hash == expected_hash

def test_p7_fts_recall_precision_audit(tmp_path):
    """Phase 7 Deep Audit: Full-text search recall precision verification"""
    clear_chroma_clients()
    hp = Hippocampus(db_dir=str(tmp_path), embed_client=DummyEmbedClient())
    
    for i in range(5):
        hp.save_trace(f"noise-{i}", {"text": f"Normal system log line {i}"}, search_text=f"Normal log {i}")
    
    target_fact = "CRITICAL_SECURITY_EVENT: Port 22 opened by user 'admin-root'"
    hp.save_trace("target-99", {"text": target_fact}, search_text=target_fact)
    
    # Perform search
    results = hp.search("admin-root")
    
    expected_list = "['target-99']"
    actual_list = str(results)
    
    visual_audit_high_fid(
        "FTS Recall Precision",
        "Search hyphenated word 'admin-root' in 6 logs",
        expected_list,
        actual_list
    )
    
    assert len(results) >= 1
    assert results[0] == "target-99"
