# Generated from design/management_api.md v1.0
import pytest
import os
import shutil
import asyncio
from fastapi.testclient import TestClient
from src.main import app

TEST_DB_DIR = "/home/nvidia/ClawBrain/tests/data/p17_tmp"

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

def test_p17_get_memory_state_structure():
    """GET /v1/memory/{session_id} 返回结构完整"""
    if os.path.exists(TEST_DB_DIR): shutil.rmtree(TEST_DB_DIR)
    os.environ["CLAWBRAIN_DB_DIR"] = TEST_DB_DIR

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

def test_p17_delete_clears_summary():
    """DELETE /v1/memory/{session_id} 清除新皮层摘要"""
    if os.path.exists(TEST_DB_DIR): shutil.rmtree(TEST_DB_DIR)
    os.environ["CLAWBRAIN_DB_DIR"] = TEST_DB_DIR

    with TestClient(app) as client:
        # 先写入摘要
        mr = client.app.state.memory_router
        mr.neo._save_summary("del_session", "This summary should be deleted")

        # 确认摘要存在
        before = client.get("/v1/memory/del_session").json()
        visual_audit("DELETE: Before", "Summary exists before delete", True, before["neocortex_summary"] is not None)

        # 执行删除
        del_resp = client.delete("/v1/memory/del_session")
        visual_audit("DELETE: Status", "Should return 200", 200, del_resp.status_code)
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "cleared"

        # 确认摘要已清除
        after = client.get("/v1/memory/del_session").json()
        visual_audit("DELETE: After", "Summary should be null after delete", None, after["neocortex_summary"])
        assert after["neocortex_summary"] is None

def test_p17_manual_distill_trigger():
    """POST /v1/memory/{session_id}/distill 立即返回 triggered 状态"""
    if os.path.exists(TEST_DB_DIR): shutil.rmtree(TEST_DB_DIR)
    os.environ["CLAWBRAIN_DB_DIR"] = TEST_DB_DIR

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
    """健康检查版本号已更新至 1.42"""
    with TestClient(app) as client:
        resp = client.get("/health")
        data = resp.json()
        visual_audit("Health Check Version", "version should be 1.42", "1.42", data.get("version"))
        assert resp.status_code == 200
        assert data["version"] == "1.42"
