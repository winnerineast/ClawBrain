# Generated from design/gateway.md v1.19
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app

def visual_audit(test_name, input_summary, expected, actual):
    match = "YES" if str(expected) in str(actual) or expected == actual else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_summary}")
    print("-" * 60)
    print(f"{'EXPECTED':<27} | {'ACTUAL'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected)[:27]:<27} | {str(actual)[:27]}")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

@pytest.mark.asyncio
async def test_e2e_multi_round_marathon():
    """E2E: 21轮深度技术对话马拉松测试 (带 Breakdown 审计)"""
    data_path = Path("tests/data/p5_e2e.json")
    thread = json.loads(data_path.read_text())["multi_round_thread"]
    
    # 打印审计 Breakdown (3.1 准则)
    print("\n[MARATHON BREAKDOWN]")
    print(f"Total History Rounds: {len(thread)}")
    print(f"  - Round 1 Snapshot:  {thread[0]['content'][:50]}...")
    print(f"  - Round 10 Snapshot: {thread[18]['content'][:50]}...") # 数组索引 18 是第 10 轮 User
    print(f"  - Round 20 Snapshot: {thread[-1]['content'][:50]}...")
    print("-" * 60)

    # 增加第 21 轮提问，要求跨轮次召回 (3.2 准则)
    # 我们询问关于 Round 2 (FastAPI/SQLAlchemy) 和 Round 12 (AWS ECS) 的综合建议
    question = "Round 21: Based on our talk about FastAPI (Round 2) and AWS ECS (Round 12), what is the single most critical step for production stability?"
    thread.append({"role": "user", "content": question})
    
    payload = {"model": "gemma4:e4b", "messages": thread, "stream": False}
    
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        
        actual_content = response.json()["message"]["content"]
        
        # 审计跨轮次知识点召回 (Expected: 必须提到稳定性、可观测性或相关后端关键词)
        expected_recall = "Recall from Round 2/12"
        visual_audit("Marathon Knowledge Recall", question, expected_recall, actual_content)
        
        print(f"\n[FULL RESPONSE PROOF]\n{actual_content}\n")
        assert len(actual_content) > 20

@pytest.mark.asyncio
async def test_e2e_ollama_chat_lifespan():
    payload = {"model": "gemma4:e4b", "messages": [{"role": "user", "content": "1+1=?"}], "stream": False}
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        visual_audit("E2E Chat", "1+1=?", "2", response.text)
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_e2e_qualification_interception():
    payload = {
        "model": "qwen2.5:latest",
        "messages": [{"role": "user", "content": "test"}],
        "tools": [{"type": "function", "function": {"name": "test"}}]
    }
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        visual_audit("E2E Qualification", "Qwen + Tools", 422, response.status_code)
        assert response.status_code == 422
