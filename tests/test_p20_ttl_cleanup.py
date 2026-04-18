# Generated from design/memory_hippocampus.md v1.8
import pytest
import os
import shutil
import time
from pathlib import Path
from src.memory.storage import Hippocampus, clear_chroma_clients

def visual_audit(test_name, description, expected, actual):
    match = "YES" if str(expected) == str(actual) else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("=" * 70)
    print(f"DESCRIPTION: {description}")
    print("-" * 70)
    print(f"{'EXPECTED':<33} | {'ACTUAL'}")
    print(f"{str(expected)[:33]:<33} | {str(actual)[:33]}")
    print("-" * 70)
    print(f"MATCH: {match}")
    print("=" * 70)

# ── P20-A: Dirty data purge (timestamp=0.0) ──────────────────────────────

def test_p20_dirty_data_purged_on_init(tmp_path):
    """Dirty records with timestamp=0.0 must be automatically cleared during the next Hippocampus initialization"""
    clear_chroma_clients()
    hp = Hippocampus(db_dir=str(tmp_path))
    
    # Manually insert dirty records into ChromaDB
    hp.traces_col.add(
        ids=["dirty-1", "dirty-2", "clean-1"],
        documents=['{"dirty": true}', '{"dirty": true}', '{"clean": true}'],
        metadatas=[
            {"timestamp": 0.0, "session_id": "default"},
            {"timestamp": 0.0, "session_id": "default"},
            {"timestamp": time.time(), "session_id": "default"}
        ]
    )

    # Re-initialize -> Trigger _startup_cleanup
    clear_chroma_clients()
    hp2 = Hippocampus(db_dir=str(tmp_path))
    
    res = hp2.traces_col.get()
    all_ids = res["ids"]

    visual_audit("Dirty purge: dirty-1 removed", "timestamp=0.0 record must be gone",
                 False, "dirty-1" in all_ids)
    visual_audit("Dirty purge: dirty-2 removed", "timestamp=0.0 record must be gone",
                 False, "dirty-2" in all_ids)
    visual_audit("Dirty purge: clean-1 kept", "valid record must survive",
                 True, "clean-1" in all_ids)

    assert "dirty-1" not in all_ids
    assert "dirty-2" not in all_ids
    assert "clean-1" in all_ids

# ── P20-B: TTL Expiry Purge ───────────────────────────────────────────────

def test_p20_ttl_expired_traces_purged(tmp_path):
    """Valid records exceeding TTL should be cleared; non-expired records must be retained"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_TRACE_TTL_DAYS"] = "1"  # 1 day

    hp = Hippocampus(db_dir=str(tmp_path))

    # Manually insert records
    three_days_ago = time.time() - 3 * 86400
    hp.traces_col.add(
        ids=["expired-1", "fresh-1"],
        documents=['{"old": true}', '{"new": true}'],
        metadatas=[
            {"timestamp": three_days_ago, "session_id": "default"},
            {"timestamp": time.time(), "session_id": "default"}
        ]
    )

    # Re-initialize -> Trigger TTL cleanup
    clear_chroma_clients()
    hp2 = Hippocampus(db_dir=str(tmp_path))
    
    all_ids = hp2.traces_col.get()["ids"]

    if "CLAWBRAIN_TRACE_TTL_DAYS" in os.environ:
        del os.environ["CLAWBRAIN_TRACE_TTL_DAYS"]

    visual_audit("TTL: expired-1 purged", "3-day-old record with TTL=1d must be gone",
                 False, "expired-1" in all_ids)
    visual_audit("TTL: fresh-1 kept", "recent record must survive",
                 True, "fresh-1" in all_ids)

    assert "expired-1" not in all_ids
    assert "fresh-1" in all_ids

def test_p20_ttl_zero_disables_expiry(tmp_path):
    """CLAWBRAIN_TRACE_TTL_DAYS=0 should disable TTL, all valid records retained"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_TRACE_TTL_DAYS"] = "0"

    hp = Hippocampus(db_dir=str(tmp_path))
    old_ts = time.time() - 365 * 86400  # 1 year ago
    hp.traces_col.add(
        ids=["old-no-ttl"],
        documents=['{"ancient": true}'],
        metadatas=[{"timestamp": old_ts, "session_id": "default"}]
    )

    clear_chroma_clients()
    hp2 = Hippocampus(db_dir=str(tmp_path))
    all_ids = hp2.traces_col.get()["ids"]

    if "CLAWBRAIN_TRACE_TTL_DAYS" in os.environ:
        del os.environ["CLAWBRAIN_TRACE_TTL_DAYS"]

    visual_audit("TTL=0: old record kept", "TTL disabled, 1-year-old record must survive",
                 True, "old-no-ttl" in all_ids)

    assert "old-no-ttl" in all_ids

# ── P20-C: Orphan blob cleanup ──────────────────────────────────────────

def test_p20_orphan_blobs_deleted(tmp_path):
    """Files in the blobs/ directory without corresponding traces records must be cleared"""
    clear_chroma_clients()
    hp = Hippocampus(db_dir=str(tmp_path))

    # Write a "real" blob trace
    hp.save_trace("real-blob", {"data": "x" * 1024}, threshold=1, session_id="s1")

    # Manually write an orphan blob file
    orphan_path = hp.blob_dir / "orphan-abc123.json"
    orphan_path.write_text('{"orphan": true}')

    visual_audit("Before cleanup: orphan exists",
                 "orphan file present before re-init",
                 True, orphan_path.exists())
    assert orphan_path.exists()

    # Re-initialize -> Trigger orphan cleanup
    clear_chroma_clients()
    hp2 = Hippocampus(db_dir=str(tmp_path))

    visual_audit("After cleanup: orphan removed",
                 "orphan blob must be deleted on re-init",
                 False, orphan_path.exists())
    visual_audit("After cleanup: real blob kept",
                 "blob with valid traces record must survive",
                 True, (hp2.blob_dir / "real-blob.json").exists())

    assert not orphan_path.exists()
    assert (hp2.blob_dir / "real-blob.json").exists()

# ── P20-D: Legacy SQLite cleanup verification ──────────────────────────

def test_p20_legacy_sqlite_cleanup(tmp_path):
    """Ensure that the startup cleanup also clears legacy SQLite data if found (transition aid)"""
    clear_chroma_clients()
    db_dir = str(tmp_path)
    db_path = Path(db_dir) / "hippocampus.db"
    
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE traces (trace_id TEXT PRIMARY KEY, timestamp REAL)")
        conn.execute("INSERT INTO traces VALUES ('legacy-dirty', 0.0)")
        conn.execute(f"INSERT INTO traces VALUES ('legacy-clean', {time.time()})")
        
    hp = Hippocampus(db_dir=db_dir)
    
    with sqlite3.connect(db_path) as conn:
        all_ids = [r[0] for r in conn.execute("SELECT trace_id FROM traces").fetchall()]
        
    visual_audit("Legacy Purge: dirty gone", "legacy SQLite dirty records should be purged",
                 False, "legacy-dirty" in all_ids)
    visual_audit("Legacy Purge: clean kept", "legacy SQLite clean records preserved",
                 True, "legacy-clean" in all_ids)
                 
    assert "legacy-dirty" not in all_ids
    assert "legacy-clean" in all_ids
