# Generated from design/gateway.md v1.11
import pytest
from fastapi.testclient import TestClient
from src.main import app
import json

client = TestClient(app)

def audit_log(test_name, path, expected_status, actual_status):
    print(f"\n[AUDIT START: {test_name}]")
    print(f"Path: {path}")
    print(f"Expected Status: {expected_status}")
    print(f"Actual Status:   {actual_status}")
    print("[AUDIT END]")

def test_ollama_path_routing():
    """验证 /api/* 路径正确路由到 Ollama 处理逻辑"""
    # 模拟一个会触发 502 (因为后端没开) 的真实转发请求
    # 如果返回 502 而不是 404，说明路由成功到达了 Adapter
    response = client.post("/api/chat", json={"model": "gemma4:e4b", "messages": []})
    audit_log("Ollama Routing", "/api/chat", "502 or 200", response.status_code)
    assert response.status_code in [200, 502, 422]

def test_openai_path_routing():
    """验证 /v1/* 路径正确分发并返回 501 (Stub)"""
    response = client.post("/v1/chat/completions", json={"model": "gpt-4", "messages": []})
    audit_log("OpenAI Routing", "/v1/chat/completions", 501, response.status_code)
    assert response.status_code == 501

def test_invalid_path():
    """验证非法路径返回 404"""
    response = client.get("/invalid/path")
    audit_log("Invalid Path", "/invalid/path", 404, response.status_code)
    assert response.status_code == 404

def test_health_check():
    """验证基础健康检查"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["proxy"] == "ClawBrain"
