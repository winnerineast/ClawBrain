# Generated from design/memory_hippocampus.md v1.8
import pytest
import os
import shutil
import sqlite3
import time
from pathlib import Path
from src.memory.storage import Hippocampus

TEST_DIR = "/home/nvidia/ClawBrain/tests/data/p20_tmp"

def setup_function():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

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

# ── P20-A: 脏数据清除（timestamp=0.0）────────────────────────────────────────

def test_p20_dirty_data_purged_on_init():
    """timestamp=0.0 的脏记录必须在下次 Hippocampus 初始化时被自动清除"""
    # 先手动插入脏记录（绕过 save_trace 以模拟旧 bug）
    hp = Hippocampus(db_dir=TEST_DIR)
    with sqlite3.connect(hp.db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("dirty-1", 0.0, "", 0, "", '{"dirty": true}', "abc", "default")
        )
        conn.execute(
            "INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("dirty-2", 0.0, "", 0, "", '{"dirty": true}', "def", "default")
        )
        # 正常记录
        conn.execute(
            "INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("clean-1", time.time(), "", 0, "", '{"clean": true}', "ghi", "default")
        )

    # 重新初始化 → 触发 _startup_cleanup
    hp2 = Hippocampus(db_dir=TEST_DIR)
    with sqlite3.connect(hp2.db_path) as conn:
        all_ids = [r[0] for r in conn.execute("SELECT trace_id FROM traces").fetchall()]

    visual_audit("Dirty purge: dirty-1 removed", "timestamp=0.0 record must be gone",
                 False, "dirty-1" in all_ids)
    visual_audit("Dirty purge: dirty-2 removed", "timestamp=0.0 record must be gone",
                 False, "dirty-2" in all_ids)
    visual_audit("Dirty purge: clean-1 kept", "valid record must survive",
                 True, "clean-1" in all_ids)

    assert "dirty-1" not in all_ids
    assert "dirty-2" not in all_ids
    assert "clean-1" in all_ids

# ── P20-B: TTL 过期清除 ────────────────────────────────────────────────────

def test_p20_ttl_expired_traces_purged():
    """超过 TTL 的有效记录应被清除；未过期记录必须保留"""
    os.environ["CLAWBRAIN_TRACE_TTL_DAYS"] = "1"  # 1 天

    hp = Hippocampus(db_dir=TEST_DIR)

    # 手动插入一条"3天前"的记录（已过期）
    three_days_ago = time.time() - 3 * 86400
    with sqlite3.connect(hp.db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("expired-1", three_days_ago, "", 0, "", '{"old": true}', "xxx", "default")
        )
        # 新鲜记录
        conn.execute(
            "INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("fresh-1", time.time(), "", 0, "", '{"new": true}', "yyy", "default")
        )

    # 重新初始化 → 触发 TTL 清理
    hp2 = Hippocampus(db_dir=TEST_DIR)
    with sqlite3.connect(hp2.db_path) as conn:
        all_ids = [r[0] for r in conn.execute("SELECT trace_id FROM traces").fetchall()]

    del os.environ["CLAWBRAIN_TRACE_TTL_DAYS"]

    visual_audit("TTL: expired-1 purged", "3-day-old record with TTL=1d must be gone",
                 False, "expired-1" in all_ids)
    visual_audit("TTL: fresh-1 kept", "recent record must survive",
                 True, "fresh-1" in all_ids)

    assert "expired-1" not in all_ids
    assert "fresh-1" in all_ids

def test_p20_ttl_zero_disables_expiry():
    """CLAWBRAIN_TRACE_TTL_DAYS=0 应禁用 TTL，所有有效记录保留"""
    os.environ["CLAWBRAIN_TRACE_TTL_DAYS"] = "0"

    hp = Hippocampus(db_dir=TEST_DIR)
    old_ts = time.time() - 365 * 86400  # 1 年前
    with sqlite3.connect(hp.db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("old-no-ttl", old_ts, "", 0, "", '{"ancient": true}', "zzz", "default")
        )

    hp2 = Hippocampus(db_dir=TEST_DIR)
    with sqlite3.connect(hp2.db_path) as conn:
        all_ids = [r[0] for r in conn.execute("SELECT trace_id FROM traces").fetchall()]

    del os.environ["CLAWBRAIN_TRACE_TTL_DAYS"]

    visual_audit("TTL=0: old record kept", "TTL disabled, 1-year-old record must survive",
                 True, "old-no-ttl" in all_ids)

    assert "old-no-ttl" in all_ids

# ── P20-C: 孤儿 blob 清理 ─────────────────────────────────────────────────

def test_p20_orphan_blobs_deleted():
    """blobs/ 目录中无对应 traces 记录的文件必须被清除"""
    hp = Hippocampus(db_dir=TEST_DIR)

    # 写一个"真实"的 blob trace
    hp.save_trace("real-blob", {"data": "x" * 1024}, threshold=1, context_id="s1")

    # 手动写入一个孤儿 blob 文件
    orphan_path = hp.blob_dir / "orphan-abc123.json"
    orphan_path.write_text('{"orphan": true}')

    visual_audit("Before cleanup: orphan exists",
                 "orphan file present before re-init",
                 True, orphan_path.exists())
    assert orphan_path.exists()

    # 重新初始化 → 触发孤儿清理
    hp2 = Hippocampus(db_dir=TEST_DIR)

    visual_audit("After cleanup: orphan removed",
                 "orphan blob must be deleted on re-init",
                 False, orphan_path.exists())
    visual_audit("After cleanup: real blob kept",
                 "blob with valid traces record must survive",
                 True, Path(hp2.blob_dir / "real-blob.json").exists())

    assert not orphan_path.exists()
    assert (hp2.blob_dir / "real-blob.json").exists()

# ── P20-D: 生产 DB 迁移验证 ───────────────────────────────────────────────

def test_p20_production_db_migration():
    """生产 DB（无 context_id 列）能正确迁移并清除脏数据"""
    PROD_DB_DIR = "/home/nvidia/ClawBrain/tests/data/p20_prod_sim"
    if os.path.exists(PROD_DB_DIR):
        shutil.rmtree(PROD_DB_DIR)
    os.makedirs(PROD_DB_DIR)

    prod_db = Path(PROD_DB_DIR) / "hippocampus.db"

    # 模拟旧版 DB（无 checksum / context_id 列）
    with sqlite3.connect(prod_db) as conn:
        conn.execute("""
            CREATE TABLE traces (
                trace_id TEXT PRIMARY KEY,
                timestamp REAL,
                model TEXT,
                is_blob INTEGER,
                blob_path TEXT,
                raw_content TEXT
            )
        """)
        conn.execute("CREATE VIRTUAL TABLE search_idx USING fts5(trace_id UNINDEXED, content)")
        # 脏数据
        conn.execute("INSERT INTO traces VALUES ('legacy-dirty', 0.0, '', 0, '', '{}')")
        # 正常数据
        conn.execute(f"INSERT INTO traces VALUES ('legacy-clean', {time.time()}, '', 0, '', '{{\"ok\": 1}}')")

    # 用新版 Hippocampus 初始化（触发迁移 + 清理）
    hp = Hippocampus(db_dir=PROD_DB_DIR)

    with sqlite3.connect(hp.db_path) as conn:
        all_ids = [r[0] for r in conn.execute("SELECT trace_id FROM traces").fetchall()]
        cols = [c[1] for c in conn.execute("PRAGMA table_info(traces)").fetchall()]

    visual_audit("Migration: context_id column added", "schema must have context_id",
                 True, "context_id" in cols)
    visual_audit("Migration: legacy-dirty removed", "dirty record purged after migration",
                 False, "legacy-dirty" in all_ids)
    visual_audit("Migration: legacy-clean kept", "valid record preserved",
                 True, "legacy-clean" in all_ids)

    assert "context_id" in cols
    assert "legacy-dirty" not in all_ids
    assert "legacy-clean" in all_ids

    shutil.rmtree(PROD_DB_DIR)
