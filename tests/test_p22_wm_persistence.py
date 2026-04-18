# Generated from design/memory_working.md v1.4 / design/memory_router.md v1.11
import pytest
import os
import asyncio
from src.memory.storage import Hippocampus, clear_chroma_clients
from src.memory.router import MemoryRouter

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
async def test_p22_wm_state_written_after_ingest(tmp_path):
    """There should be corresponding records in ChromaDB wm_col after ingest"""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()
    await router.ingest(
        {"messages": [{"role": "user", "content": "hello persistence test"}]},
        session_id="session-A"
    )

    # Check ChromaDB
    res = router.hippo.wm_col.get(where={"session_id": "session-A"})
    metas = res["metadatas"]

    visual_audit("wm_state rows after ingest", "should have ≥1 row", True, len(metas) > 0)
    visual_audit("wm_state activation range", "activation should be 0..1", True,
                 all(0.0 <= m["activation"] <= 1.0 for m in metas))

    assert len(metas) > 0
    assert all(0.0 <= m["activation"] <= 1.0 for m in metas)

# ── P22-B: Exact activation restoration across restarts ───────────────────

@pytest.mark.asyncio
async def test_p22_exact_activation_restored_after_restart(tmp_path):
    """The activation value of WM after restart should be exactly the same as before restart"""
    clear_chroma_clients()
    router1 = MemoryRouter(db_dir=str(tmp_path))
    await router1.wait_until_ready()
    await router1.ingest(
        {"messages": [{"role": "user", "content": "topic ALPHA project detail"}]},
        session_id="persist-session"
    )
    await router1.ingest(
        {"messages": [{"role": "user", "content": "unrelated item XYZ"}]},
        session_id="persist-session"
    )

    # Get WM state (activation + trace_ids) before restart
    wm_before = router1._get_wm("persist-session").items
    before_state = {it.trace_id: round(it.activation, 4) for it in wm_before}

    visual_audit("Before restart: WM item count",
                 "should have 2 items", 2, len(wm_before))
    
    # Simulate restart
    clear_chroma_clients()
    router2 = MemoryRouter(db_dir=str(tmp_path))
    await router2.wait_until_ready()
    wm_after = router2._get_wm("persist-session").items
    after_state = {it.trace_id: round(it.activation, 4) for it in wm_after}

    visual_audit("After restart: activations match exactly",
                 "activation values identical after restore",
                 before_state, after_state)

    assert len(after_state) == len(before_state)
    assert after_state == before_state

# ── P22-C: Multi-session snapshots are isolated ──────────────────────────

@pytest.mark.asyncio
async def test_p22_multi_session_snapshots_isolated(tmp_path):
    """wm_state rows of different sessions do not pollute each other"""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()
    await router.ingest(
        {"messages": [{"role": "user", "content": "Alice working on PROJECT-A"}]},
        session_id="alice"
    )
    await router.ingest(
        {"messages": [{"role": "user", "content": "Bob working on PROJECT-B"}]},
        session_id="bob"
    )

    alice_res = router.hippo.wm_col.get(where={"session_id": "alice"})
    bob_res = router.hippo.wm_col.get(where={"session_id": "bob"})
    
    alice_docs = alice_res["documents"]
    bob_docs = bob_res["documents"]

    alice_has_bob = any("PROJECT-B" in d for d in alice_docs)
    bob_has_alice = any("PROJECT-A" in d for d in bob_docs)

    visual_audit("Alice snapshot: no Bob content", "PROJECT-B absent in alice wm_state",
                 False, alice_has_bob)
    visual_audit("Bob snapshot: no Alice content", "PROJECT-A absent in bob wm_state",
                 False, bob_has_alice)

    assert not alice_has_bob
    assert not bob_has_alice

# ── P22-D: clear_wm_state clears snapshots ──────────────────────────────

@pytest.mark.asyncio
async def test_p22_clear_wm_state(tmp_path):
    """clear_wm_state should delete all wm_state rows for the specified session"""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()
    await router.ingest(
        {"messages": [{"role": "user", "content": "content to be cleared"}]},
        session_id="clear-session"
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
async def test_p22_snapshot_takes_priority_over_traces_rebuild(tmp_path):
    """_hydrate does not take the traces rebuild path when a snapshot exists; fall back to traces rebuild when no snapshot exists"""
    clear_chroma_clients()
    router1 = MemoryRouter(db_dir=str(tmp_path))
    await router1.wait_until_ready()
    await router1.ingest(
        {"messages": [{"role": "user", "content": "snapshot priority test CANARY"}]},
        session_id="snap-test"
    )

    # Verify snapshot exists
    snap = router1.hippo.load_wm_state("snap-test")
    assert len(snap) > 0, "Snapshot must exist before restart"

    # Restart — should take snapshot path
    clear_chroma_clients()
    router2 = MemoryRouter(db_dir=str(tmp_path))
    await router2.wait_until_ready()
    wm_contents = router2._get_wm("snap-test").get_active_contents()
    has_canary = any("CANARY" in c for c in wm_contents)

    visual_audit("Snapshot priority: CANARY in WM after restart",
                 "content restored via snapshot path",
                 True, has_canary)
    assert has_canary

    # Manually delete snapshot and restart — fallback to traces rebuild
    router2.hippo.clear_wm_state("snap-test")
    clear_chroma_clients()
    router3 = MemoryRouter(db_dir=str(tmp_path))
    await router3.wait_until_ready()
    wm_fallback = router3._get_wm("snap-test").get_active_contents()
    has_canary_fallback = any("CANARY" in c for c in wm_fallback)

    visual_audit("Fallback rebuild: CANARY in WM after snapshot cleared",
                 "content rebuilt from traces (fallback)",
                 True, has_canary_fallback)
    assert has_canary_fallback
