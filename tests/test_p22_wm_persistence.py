# Generated from design/memory_working.md v1.4 / design/memory_router.md v1.11
import pytest
import os
import shutil
import asyncio
import sqlite3
import time
from src.memory.storage import Hippocampus
from src.memory.router import MemoryRouter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = os.path.join(PROJECT_ROOT, "tests/data/p22_tmp")

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

# ── P22-A: wm_state table write verification ─────────────────────────────

@pytest.mark.asyncio
async def test_p22_wm_state_written_after_ingest():
    """There should be corresponding records in the wm_state table after ingest"""
    router = MemoryRouter(db_dir=TEST_DIR)
    await router.ingest(
        {"messages": [{"role": "user", "content": "hello persistence test"}]},
        context_id="session-A"
    )

    with sqlite3.connect(router.hippo.db_path) as conn:
        rows = conn.execute(
            "SELECT trace_id, content, activation, timestamp FROM wm_state WHERE session_id='session-A'"
        ).fetchall()

    visual_audit("wm_state rows after ingest", "should have ≥1 row", True, len(rows) > 0)
    visual_audit("wm_state activation range", "activation should be 0..1", True,
                 all(0.0 <= r[2] <= 1.0 for r in rows))

    assert len(rows) > 0
    assert all(0.0 <= r[2] <= 1.0 for r in rows)

# ── P22-B: Exact activation restoration across restarts ───────────────────

@pytest.mark.asyncio
async def test_p22_exact_activation_restored_after_restart():
    """The activation value of WM after restart should be exactly the same as before restart"""
    router1 = MemoryRouter(db_dir=TEST_DIR)
    await router1.ingest(
        {"messages": [{"role": "user", "content": "topic ALPHA project detail"}]},
        context_id="persist-session"
    )
    await router1.ingest(
        {"messages": [{"role": "user", "content": "unrelated item XYZ"}]},
        context_id="persist-session"
    )

    # Get WM state (activation + trace_ids) before restart
    wm_before = router1._get_wm("persist-session").items
    before_state = {it.trace_id: round(it.activation, 4) for it in wm_before}

    visual_audit("Before restart: WM item count",
                 "should have 2 items", 2, len(wm_before))
    print(f"  Before activations: {before_state}")

    # Simulate restart
    router2 = MemoryRouter(db_dir=TEST_DIR)
    wm_after = router2._get_wm("persist-session").items
    after_state = {it.trace_id: round(it.activation, 4) for it in wm_after}

    print(f"  After  activations: {after_state}")

    visual_audit("After restart: WM item count matches",
                 "exact same number of items", len(before_state), len(after_state))
    visual_audit("After restart: activations match exactly",
                 "activation values identical after restore",
                 before_state, after_state)

    assert len(after_state) == len(before_state)
    assert after_state == before_state

# ── P22-C: Multi-session snapshots are isolated ──────────────────────────

@pytest.mark.asyncio
async def test_p22_multi_session_snapshots_isolated():
    """wm_state rows of different sessions do not pollute each other"""
    router = MemoryRouter(db_dir=TEST_DIR)
    await router.ingest(
        {"messages": [{"role": "user", "content": "Alice working on PROJECT-A"}]},
        context_id="alice"
    )
    await router.ingest(
        {"messages": [{"role": "user", "content": "Bob working on PROJECT-B"}]},
        context_id="bob"
    )

    with sqlite3.connect(router.hippo.db_path) as conn:
        alice_rows = conn.execute(
            "SELECT content FROM wm_state WHERE session_id='alice'"
        ).fetchall()
        bob_rows = conn.execute(
            "SELECT content FROM wm_state WHERE session_id='bob'"
        ).fetchall()

    alice_has_bob = any("PROJECT-B" in r[0] for r in alice_rows)
    bob_has_alice = any("PROJECT-A" in r[0] for r in bob_rows)

    visual_audit("Alice snapshot: no Bob content", "PROJECT-B absent in alice wm_state",
                 False, alice_has_bob)
    visual_audit("Bob snapshot: no Alice content", "PROJECT-A absent in bob wm_state",
                 False, bob_has_alice)

    assert not alice_has_bob
    assert not bob_has_alice

# ── P22-D: clear_wm_state clears snapshots ──────────────────────────────

@pytest.mark.asyncio
async def test_p22_clear_wm_state():
    """clear_wm_state should delete all wm_state rows for the specified session"""
    router = MemoryRouter(db_dir=TEST_DIR)
    await router.ingest(
        {"messages": [{"role": "user", "content": "content to be cleared"}]},
        context_id="clear-session"
    )

    # Confirm write
    before = router.hippo.load_wm_state("clear-session")
    visual_audit("Before clear: has rows", "wm_state should have rows", True, len(before) > 0)
    assert len(before) > 0

    # Clear
    router.hippo.clear_wm_state("clear-session")
    after = router.hippo.load_wm_state("clear-session")

    visual_audit("After clear: no rows", "wm_state should be empty", 0, len(after))
    assert len(after) == 0

# ── P22-E: Snapshot takes priority over traces rebuild ──────────────────

@pytest.mark.asyncio
async def test_p22_snapshot_takes_priority_over_traces_rebuild():
    """_hydrate does not take the traces rebuild path when a snapshot exists; fall back to traces rebuild when no snapshot exists"""
    router1 = MemoryRouter(db_dir=TEST_DIR)
    await router1.ingest(
        {"messages": [{"role": "user", "content": "snapshot priority test CANARY"}]},
        context_id="snap-test"
    )

    # Verify snapshot exists
    snap = router1.hippo.load_wm_state("snap-test")
    assert len(snap) > 0, "Snapshot must exist before restart"

    # Restart — should take snapshot path
    router2 = MemoryRouter(db_dir=TEST_DIR)
    wm_contents = router2._get_wm("snap-test").get_active_contents()
    has_canary = any("CANARY" in c for c in wm_contents)

    visual_audit("Snapshot priority: CANARY in WM after restart",
                 "content restored via snapshot path",
                 True, has_canary)
    assert has_canary

    # Manually delete snapshot and restart — fallback to traces rebuild
    router2.hippo.clear_wm_state("snap-test")
    router3 = MemoryRouter(db_dir=TEST_DIR)
    wm_fallback = router3._get_wm("snap-test").get_active_contents()
    has_canary_fallback = any("CANARY" in c for c in wm_fallback)

    visual_audit("Fallback rebuild: CANARY in WM after snapshot cleared",
                 "content rebuilt from traces (fallback)",
                 True, has_canary_fallback)
    assert has_canary_fallback
