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
