# Generated from design/gateway.md v1.34
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app

def visual_audit(test_name, input_summary, expected_keywords, actual):
    # 3.2 准则修正：改进匹配逻辑，支持关键词列表
    found = any(kw.lower() in str(actual).lower() for kw in expected_keywords)
    match_status = "YES" if found else "NO"
    
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_summary}")
    print("-" * 60)
    print(f"{'EXPECTED KEYWORDS':<27} | {'ACTUAL (SNIPPET)'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected_keywords):<27} | {str(actual)[:27].replace('\n', ' ')}")
    print("-" * 60)
    print(f"MATCH: {match_status}")
    print("=" * 60)
    return found

@pytest.mark.asyncio
async def test_e2e_multi_round_marathon():
    """E2E: 21轮长对话马拉松测试 (强化硬断言)"""
    data_path = Path("tests/data/p5_e2e.json")
    thread = json.loads(data_path.read_text())["multi_round_thread"]
    
    question = "Round 21: Based on our talk about FastAPI (Round 2) and AWS ECS (Round 12), what is the single most critical step for production stability?"
    thread.append({"role": "user", "content": question})
    
    payload = {"model": "gemma4:e4b", "messages": thread, "stream": False}
    
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        actual_content = response.json()["message"]["content"]
        
        # 3.2 准则修复：定义硬断言金丝雀事实
        canary_keywords = ["FastAPI", "ECS", "ALB", "CloudWatch"]
        success = visual_audit("Marathon Knowledge Recall", question, canary_keywords, actual_content)
        
        # 强制断言：匹配失败即报错
        assert success, f"Marathon recall failed! Expected keywords {canary_keywords} not found in model response."

@pytest.mark.asyncio
async def test_e2e_ollama_chat_lifespan():
    payload = {"model": "gemma4:e4b", "messages": [{"role": "user", "content": "1+1=?"}], "stream": False}
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        # 基础数学检查
        assert "2" in response.text

@pytest.mark.asyncio
async def test_e2e_qualification_interception():
    """验证 TIER_3 模型带工具请求被 422 拦截"""
    payload = {
        "model": "qwen2.5:latest",
        "messages": [{"role": "user", "content": "test"}],
        "tools": [{"type": "function", "function": {"name": "test"}}]
    }
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
        visual_audit("E2E Qualification", "Qwen + Tools", ["422"], response.status_code)
        assert response.status_code == 422
