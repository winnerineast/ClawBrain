# Generated from design/management_api.md v1.0
import pytest
import os
import shutil
import asyncio
from fastapi.testclient import TestClient
from src.main import app
from src.memory.storage import clear_chroma_clients

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

def test_p17_get_memory_state_structure(tmp_path):
    """GET /v1/memory/{session_id} returns a complete structure"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)

    # Note: TestClient with app might share state if not careful. 
    # But since we use tmp_path, new router will be created if app restarts or we force it.
    with TestClient(app) as client:
        response = client.get("/v1/memory/test_session")
        data = response.json()

        visual_audit(
            "GET Memory State (Status)",
            "Should return HTTP 200",
            200, response.status_code
        )
        visual_audit(
            "GET Memory State (session_id)",
            "session_id field should match",
            "test_session", data.get("session_id")
        )
        visual_audit(
            "GET Memory State (keys)",
            "All required keys present",
            True,
            all(k in data for k in ["session_id", "neocortex_summary", "working_memory_count", "working_memory_preview"])
        )

        assert response.status_code == 200
        assert data["session_id"] == "test_session"
        assert "neocortex_summary" in data
        assert "working_memory_count" in data
        assert isinstance(data["working_memory_preview"], list)

def test_p17_delete_clears_summary(tmp_path):
    """DELETE /v1/memory/{session_id} clears Neocortex summary"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)

    with TestClient(app) as client:
        # Save summary first
        mr = client.app.state.memory_router
        mr.neo._save_summary("del_session", "This summary should be deleted")

        # Confirm summary exists
        before = client.get("/v1/memory/del_session").json()
        visual_audit("DELETE: Before", "Summary exists before delete", True, before["neocortex_summary"] is not None)

        # Execute delete
        del_resp = client.delete("/v1/memory/del_session")
        visual_audit("DELETE: Status", "Should return 200", 200, del_resp.status_code)
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "cleared"

        # Confirm summary is cleared
        after = client.get("/v1/memory/del_session").json()
        visual_audit("DELETE: After", "Summary should be null after delete", None, after["neocortex_summary"])
        assert after["neocortex_summary"] is None

def test_p17_manual_distill_trigger(tmp_path):
    """POST /v1/memory/{session_id}/distill immediately returns triggered status"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)

    with TestClient(app) as client:
        response = client.post("/v1/memory/distill_session/distill")
        data = response.json()

        visual_audit(
            "Manual Distill Trigger (Status)",
            "Should return HTTP 200",
            200, response.status_code
        )
        visual_audit(
            "Manual Distill Trigger (status field)",
            "status should be distillation_triggered",
            "distillation_triggered", data.get("status")
        )

        assert response.status_code == 200
        assert data["status"] == "distillation_triggered"
        assert data["session_id"] == "distill_session"

def test_p17_health_check_version():
    """Health check version number has been updated to 1.42"""
    with TestClient(app) as client:
        resp = client.get("/health")
        data = resp.json()
        visual_audit("Health Check Version", "version should be 1.42", "1.42", data.get("version"))
        assert resp.status_code == 200
        assert data["version"] == "1.42"

def test_p17_management_sessions_and_traces(tmp_path):
    """GET /v1/management/sessions and /traces are fully functional"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)

    with TestClient(app) as client:
        # 1. Ingest some data to create a session
        ingest_payload = {
            "session_id": "sid_123",
            "content": "Secret password is XYZ"
        }
        client.post("/v1/ingest", json=ingest_payload)
        
        # 2. Test Session Discovery
        resp = client.get("/v1/management/sessions")
        data = resp.json()
        assert resp.status_code == 200
        assert "sid_123" in data["sessions"]
        visual_audit("MGMT: Sessions", "Session sid_123 should be discovered", True, "sid_123" in data["sessions"])

        # 3. Test Trace Inspection
        resp = client.get("/v1/management/traces/sid_123?limit=10")
        data = resp.json()
        assert resp.status_code == 200
        assert len(data["traces"]) >= 1
        assert "XYZ" in data["traces"][0]["raw_content"]
        visual_audit("MGMT: Traces", "Trace should contain XYZ", True, "XYZ" in data["traces"][0]["raw_content"])

def test_p17_internal_assemble_v1_v2(tmp_path):
    """POST /internal/assemble correctly injects memory (Mission Critical)"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_DB_DIR"] = str(tmp_path)

    with TestClient(app) as client:
        # 1. Plant a fact
        client.post("/v1/ingest", json={"session_id": "plugin_test", "content": "The codebase is written in Rust."})
        
        # 2. Simulate Plugin Assemble Call
        assemble_payload = {
            "session_id": "plugin_test",
            "current_focus": "What language?",
            "token_budget": 500
        }
        resp = client.post("/internal/assemble", json=assemble_payload)
        data = resp.json()
        
        assert resp.status_code == 200
        assert "Rust" in data["system_prompt_addition"]
        visual_audit("PLUGIN: Assemble", "Injected prompt should contain Rust", True, "Rust" in data["system_prompt_addition"])
