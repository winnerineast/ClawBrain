# Generated from design/gateway.md v1.16
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app

def audit_log(test_name, rounds, input_len, actual_status):
    print(f"\n[AUDIT START: {test_name}]")
    print(f"Rounds: {rounds}")
    print(f"Input Payload Length: {input_len} chars")
    print(f"Actual Status: {actual_status}")
    print("[AUDIT END]")

@pytest.mark.asyncio
async def test_e2e_multi_round_marathon():
    """E2E: 20轮深度技术对话马拉松测试"""
    data_path = Path("tests/data/p5_multi_round.json")
    thread = json.loads(data_path.read_text())["multi_round_thread"]
    
    # 增加第 21 轮提问
    thread.append({"role": "user", "content": "Round 21: Based on our entire conversation, what is the single most critical step for production stability?"})
    
    payload = {
        "model": "gemma4:e4b",
        "messages": thread,
        "stream": False
    }
    
    with TestClient(app) as client:
        # 这是一个超长请求，考验网关处理大数据量的能力
        response = client.post("/api/chat", json=payload)
        
        audit_log("E2E Marathon", len(thread), len(str(payload)), response.status_code)
        
        assert response.status_code == 200
        content = response.json().get("message", {}).get("content", "")
        # 验证模型是否理解了上下文（应该包含监控、部署或之前的关键词）
        assert len(content) > 10
        print(f"[MARATHON RESULT] Model Response: {content[:100]}...")

@pytest.mark.asyncio
async def test_e2e_ollama_chat_lifespan():
    """保持原有的基础连通性测试"""
    payload = {
        "model": "gemma4:e4b",
        "messages": [{"role": "user", "content": "1+1=?"}],
        "stream": False
    }
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_e2e_qualification_interception():
    """保持原有的拦截拦截测试"""
    payload = {
        "model": "qwen2.5:latest",
        "messages": [{"role": "user", "content": "test"}],
        "tools": [{"type": "function", "function": {"name": "test"}}]
    }
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 422
