# Generated from design/memory_hippocampus.md v1.7 / design/memory_router.md v1.10
import pytest
import os
import shutil
import asyncio
from src.memory.storage import Hippocampus
from src.memory.router import MemoryRouter

TEST_DIR = "/home/nvidia/ClawBrain/tests/data/p18_tmp"

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

# ── P18-A: 海马体存储层 session 隔离 ──────────────────────────────────────

def test_p18_hippo_search_session_isolation():
    """跨 session 的内容不应互相召回"""
    hp = Hippocampus(db_dir=TEST_DIR)

    hp.save_trace("alice-1", {"x": 1}, search_text="project ALPHA secret key",    context_id="alice")
    hp.save_trace("bob-1",   {"x": 2}, search_text="project BETA confidential",    context_id="bob")
    hp.save_trace("alice-2", {"x": 3}, search_text="ALPHA deployment config",      context_id="alice")

    alice_results = hp.search("ALPHA", context_id="alice")
    bob_results   = hp.search("ALPHA", context_id="bob")

    visual_audit("Hippo Search: Alice sees ALPHA",
                 "alice should get her own ALPHA traces",
                 True, len(alice_results) > 0)
    visual_audit("Hippo Search: Bob cannot see Alice's ALPHA",
                 "bob's search for ALPHA should return nothing",
                 0, len(bob_results))

    assert len(alice_results) > 0
    assert all(r in ["alice-1", "alice-2"] for r in alice_results)
    assert len(bob_results) == 0

def test_p18_hippo_save_context_id_persisted():
    """context_id 正确写入 traces 表"""
    hp = Hippocampus(db_dir=TEST_DIR)
    hp.save_trace("trace-x", {"msg": "hello"}, search_text="hello world", context_id="session-99")

    import sqlite3
    conn = sqlite3.connect(hp.db_path)
    row = conn.execute("SELECT context_id FROM traces WHERE trace_id='trace-x'").fetchone()
    conn.close()

    visual_audit("Hippo Persist context_id",
                 "context_id should be 'session-99' in DB",
                 "session-99", row[0] if row else None)
    assert row is not None
    assert row[0] == "session-99"

def test_p18_hippo_get_recent_traces_filtered():
    """get_recent_traces 按 session 过滤"""
    hp = Hippocampus(db_dir=TEST_DIR)
    hp.save_trace("s1-t1", {"x": 1}, context_id="session-A")
    hp.save_trace("s1-t2", {"x": 2}, context_id="session-A")
    hp.save_trace("s2-t1", {"x": 3}, context_id="session-B")

    a_traces = hp.get_recent_traces(limit=10, context_id="session-A")
    b_traces = hp.get_recent_traces(limit=10, context_id="session-B")
    all_traces = hp.get_recent_traces(limit=10)

    visual_audit("get_recent_traces: session-A count", "should be 2", 2, len(a_traces))
    visual_audit("get_recent_traces: session-B count", "should be 1", 1, len(b_traces))
    visual_audit("get_recent_traces: all (no filter)",  "should be 3", 3, len(all_traces))

    assert len(a_traces) == 2
    assert len(b_traces) == 1
    assert len(all_traces) == 3

# ── P18-B: MemoryRouter 工作记忆 session 隔离 ─────────────────────────────

@pytest.mark.asyncio
async def test_p18_wm_session_isolation():
    """不同 session 的工作记忆互不干扰"""
    router = MemoryRouter(db_dir=TEST_DIR)

    await router.ingest(
        {"messages": [{"role": "user", "content": "Alice content UNIQUE-ALICE"}]},
        context_id="alice"
    )
    await router.ingest(
        {"messages": [{"role": "user", "content": "Bob content UNIQUE-BOB"}]},
        context_id="bob"
    )

    alice_wm = router._get_wm("alice").get_active_contents()
    bob_wm   = router._get_wm("bob").get_active_contents()

    alice_has_alice = any("UNIQUE-ALICE" in c for c in alice_wm)
    alice_has_bob   = any("UNIQUE-BOB"   in c for c in alice_wm)
    bob_has_bob     = any("UNIQUE-BOB"   in c for c in bob_wm)
    bob_has_alice   = any("UNIQUE-ALICE" in c for c in bob_wm)

    visual_audit("WM Alice sees her content",  "UNIQUE-ALICE in alice WM", True, alice_has_alice)
    visual_audit("WM Alice sees no Bob",        "UNIQUE-BOB not in alice WM", False, alice_has_bob)
    visual_audit("WM Bob sees his content",    "UNIQUE-BOB in bob WM", True, bob_has_bob)
    visual_audit("WM Bob sees no Alice",        "UNIQUE-ALICE not in bob WM", False, bob_has_alice)

    assert alice_has_alice
    assert not alice_has_bob
    assert bob_has_bob
    assert not bob_has_alice

@pytest.mark.asyncio
async def test_p18_get_combined_context_isolated():
    """get_combined_context 按 session 隔离，A 的上下文不含 B 的内容"""
    router = MemoryRouter(db_dir=TEST_DIR)

    await router.ingest(
        {"messages": [{"role": "user", "content": "Alice secret ALPHA-TOKEN"}]},
        context_id="alice"
    )
    await router.ingest(
        {"messages": [{"role": "user", "content": "Bob secret BETA-TOKEN"}]},
        context_id="bob"
    )

    alice_ctx = await router.get_combined_context("alice", "ALPHA-TOKEN")
    bob_ctx   = await router.get_combined_context("bob",   "BETA-TOKEN")

    visual_audit("Alice context contains ALPHA-TOKEN", "L1 WM isolation", True, "ALPHA-TOKEN" in alice_ctx)
    visual_audit("Alice context NOT contains BETA-TOKEN", "No cross-session leak", False, "BETA-TOKEN" in alice_ctx)
    visual_audit("Bob context contains BETA-TOKEN", "L1 WM isolation", True, "BETA-TOKEN" in bob_ctx)
    visual_audit("Bob context NOT contains ALPHA-TOKEN", "No cross-session leak", False, "ALPHA-TOKEN" in bob_ctx)

    assert "ALPHA-TOKEN" in alice_ctx
    assert "BETA-TOKEN" not in alice_ctx
    assert "BETA-TOKEN" in bob_ctx
    assert "ALPHA-TOKEN" not in bob_ctx

# ── P18-C: Hydrate 按 session 恢复 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_p18_hydrate_per_session():
    """重启后 _hydrate 按 session 分别恢复 WM"""
    # 第一个 router 写入数据
    router1 = MemoryRouter(db_dir=TEST_DIR)
    await router1.ingest(
        {"messages": [{"role": "user", "content": "Hydrate ALICE persist test"}]},
        context_id="hydrate-alice"
    )
    await router1.ingest(
        {"messages": [{"role": "user", "content": "Hydrate BOB persist test"}]},
        context_id="hydrate-bob"
    )

    # 第二个 router 模拟重启，触发 _hydrate
    router2 = MemoryRouter(db_dir=TEST_DIR)

    alice_wm = router2._get_wm("hydrate-alice").get_active_contents()
    bob_wm   = router2._get_wm("hydrate-bob").get_active_contents()

    visual_audit("Hydrate: alice WM restored", "ALICE content in WM after restart",
                 True, any("ALICE" in c for c in alice_wm))
    visual_audit("Hydrate: bob WM restored",   "BOB content in WM after restart",
                 True, any("BOB" in c for c in bob_wm))

    assert any("ALICE" in c for c in alice_wm)
    assert any("BOB" in c for c in bob_wm)
