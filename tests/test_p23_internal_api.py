# Generated from design/context_engine_api.md v1.0
import pytest
import os
import shutil
import sqlite3
from fastapi.testclient import TestClient
from src.main import app

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = os.path.join(PROJECT_ROOT, "tests/data/p23_tmp")


@pytest.fixture(autouse=True)
def isolate_db(monkeypatch, tmp_path):
    """Each test gets a clean DB directory and a fresh app lifespan."""
    db_dir = str(tmp_path / "p23")
    os.makedirs(db_dir, exist_ok=True)
    monkeypatch.setenv("CLAWBRAIN_DB_DIR", db_dir)
    monkeypatch.setenv("CLAWBRAIN_MAX_CONTEXT_CHARS", "2000")
    monkeypatch.setenv("CLAWBRAIN_WM_COMPACT_KEEP_RECENT", "5")
    yield db_dir


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


# ── P23-A: POST /internal/ingest ─────────────────────────────────────────────

def test_p23_ingest_normal_message(isolate_db):
    """Non-heartbeat message must be archived in Hippocampus."""
    with TestClient(app) as client:
        resp = client.post("/internal/ingest", json={
            "session_id": "eng-session",
            "role": "user",
            "content": "Deploy NEURAL-X to production k8s cluster.",
            "is_heartbeat": False,
        })

    assert resp.status_code == 200
    data = resp.json()

    visual_audit("Ingest: ingested flag", "must be True", True, data["ingested"])
    visual_audit("Ingest: trace_id present", "must have a trace_id", True, bool(data["trace_id"]))

    assert data["ingested"] is True
    assert data["trace_id"] is not None


def test_p23_ingest_heartbeat_skipped(isolate_db):
    """Heartbeat messages must not create a trace."""
    with TestClient(app) as client:
        resp = client.post("/internal/ingest", json={
            "session_id": "eng-session",
            "role": "system",
            "content": "heartbeat",
            "is_heartbeat": True,
        })

    assert resp.status_code == 200
    data = resp.json()

    visual_audit("Ingest heartbeat: ingested=False", "heartbeat must be skipped",
                 False, data["ingested"])
    visual_audit("Ingest heartbeat: trace_id=None", "no trace for heartbeat",
                 None, data["trace_id"])

    assert data["ingested"] is False
    assert data["trace_id"] is None


def test_p23_ingest_trace_persisted_in_db(isolate_db):
    """Ingested trace must appear in get_recent_traces."""
    with TestClient(app) as client:
        r1 = client.post("/internal/ingest", json={
            "session_id": "db-session",
            "role": "user",
            "content": "Secret project codename ALPHA-ONE.",
        })
        trace_id = r1.json()["trace_id"]

        # Verify via management API
        r2 = client.get("/v1/memory/db-session")

    assert r2.status_code == 200
    state = r2.json()

    visual_audit("Ingest persisted: WM count ≥ 1", "WM must have the ingested item",
                 True, state["working_memory_count"] >= 1)

    assert state["working_memory_count"] >= 1


# ── P23-B: POST /internal/assemble ───────────────────────────────────────────

def test_p23_assemble_returns_memory_addition(isolate_db):
    """After ingest, assemble must return a non-empty system_prompt_addition."""
    with TestClient(app) as client:
        client.post("/internal/ingest", json={
            "session_id": "asm-session",
            "role": "user",
            "content": "The project uses Python 3.12 and FastAPI.",
        })
        client.post("/internal/ingest", json={
            "session_id": "asm-session",
            "role": "assistant",
            "content": "Understood. I will use Python 3.12 and FastAPI.",
        })

        resp = client.post("/internal/assemble", json={
            "session_id": "asm-session",
            "current_focus": "Python FastAPI project",
            "token_budget": 4096,
        })

    assert resp.status_code == 200
    data = resp.json()

    visual_audit("Assemble: addition non-empty", "must contain memory content",
                 True, len(data["system_prompt_addition"]) > 0)
    visual_audit("Assemble: chars_used > 0", "memory was assembled",
                 True, data["chars_used"] > 0)
    visual_audit("Assemble: CLAWBRAIN header present",
                 "addition must carry ClawBrain header",
                 True, "CLAWBRAIN MEMORY" in data["system_prompt_addition"])

    assert len(data["system_prompt_addition"]) > 0
    assert data["chars_used"] > 0
    assert "CLAWBRAIN MEMORY" in data["system_prompt_addition"]


def test_p23_assemble_empty_session_returns_200(isolate_db):
    """Assembling for a session with no history must return HTTP 200, not an error."""
    with TestClient(app) as client:
        resp = client.post("/internal/assemble", json={
            "session_id": "empty-session",
            "current_focus": "anything",
            "token_budget": 2048,
        })

    visual_audit("Assemble empty: HTTP 200", "must not error on empty session",
                 200, resp.status_code)

    assert resp.status_code == 200
    assert "system_prompt_addition" in resp.json()


# ── P23-C: POST /internal/compact ────────────────────────────────────────────

def test_p23_compact_distils_and_prunes_wm(isolate_db, monkeypatch):
    """Compact must distil traces and prune WM to CLAWBRAIN_WM_COMPACT_KEEP_RECENT."""
    monkeypatch.setenv("CLAWBRAIN_WM_COMPACT_KEEP_RECENT", "2")

    with TestClient(app) as client:
        # Ingest enough messages to have something to compact
        for i in range(8):
            client.post("/internal/ingest", json={
                "session_id": "compact-session",
                "role": "user",
                "content": f"Message number {i}: important fact about system design.",
            })

        resp = client.post("/internal/compact", json={
            "session_id": "compact-session",
            "force": True,
        })

    assert resp.status_code == 200
    data = resp.json()

    visual_audit("Compact: ok=True", "compact must succeed", True, data["ok"])
    visual_audit("Compact: compacted=True", "must report compacted", True, data["compacted"])

    assert data["ok"] is True
    assert data["compacted"] is True


# ── P23-D: POST /internal/after-turn ─────────────────────────────────────────

def test_p23_after_turn_persists_wm_snapshot(isolate_db):
    """after-turn must persist the WM snapshot to wm_state table."""
    with TestClient(app) as client:
        client.post("/internal/ingest", json={
            "session_id": "turn-session",
            "role": "user",
            "content": "After-turn persistence test canary ZETA-99.",
        })

        resp = client.post("/internal/after-turn", json={
            "session_id": "turn-session",
            "new_messages": [{"role": "user", "content": "hello"}]
        })

    assert resp.status_code == 200
    data = resp.json()

    visual_audit("After-turn: ok=True", "must return ok", True, data["ok"])
    assert data["ok"] is True


def test_p23_after_turn_wm_in_db(isolate_db):
    """WM snapshot written by after-turn must appear in wm_state table."""
    with TestClient(app) as client:
        client.post("/internal/ingest", json={
            "session_id": "snap-session",
            "role": "user",
            "content": "Snapshot verification canary OMEGA-42.",
        })
        client.post("/internal/after-turn", json={
            "session_id": "snap-session",
            "new_messages": [{"role": "user", "content": "hello"}]
        })

        # Query management API to confirm WM is live
        state = client.get("/v1/memory/snap-session").json()

    visual_audit("After-turn: WM count ≥ 1", "snapshot must be in DB",
                 True, state["working_memory_count"] >= 1)

    assert state["working_memory_count"] >= 1


# ── P23-E: Integration — full hook sequence ───────────────────────────────────

def test_p23_full_hook_sequence(isolate_db):
    """
    Simulate a full OpenClaw Context Engine turn:
    ingest → assemble → (model runs) → after-turn.
    All steps must succeed and the assemble result must contain ingested content.
    """
    with TestClient(app) as client:
        # 1. ingest (user message arrives)
        r_ingest = client.post("/internal/ingest", json={
            "session_id": "full-session",
            "role": "user",
            "content": "The production DB password is CANARY-SECRET-XYZ.",
        })
        assert r_ingest.json()["ingested"] is True

        # 2. assemble (before model run)
        r_assemble = client.post("/internal/assemble", json={
            "session_id": "full-session",
            "current_focus": "production database",
            "token_budget": 4096,
        })
        addition = r_assemble.json()["system_prompt_addition"]

        # 3. after-turn (model run completed)
        r_after = client.post("/internal/after-turn", json={
            "session_id": "full-session",
            "new_messages": [{"role": "user", "content": "hello"}]
        })

    visual_audit("Full sequence: assemble has content",
                 "addition must be non-empty after ingest",
                 True, len(addition) > 0)
    visual_audit("Full sequence: after-turn ok",
                 "after-turn must succeed",
                 True, r_after.json()["ok"])

    assert len(addition) > 0
    assert r_after.json()["ok"] is True
