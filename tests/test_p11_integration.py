# Generated from design/memory_integration.md v1.1
import pytest
import json
import os
import shutil
from fastapi.testclient import TestClient
from src.main import app

def visual_audit(test_name, input_data, expected, actual):
    match = "YES" if str(expected).lower() in str(actual).lower() or expected == actual else "NO"
    print(f"\n[AUDIT: {test_name}]")
    print("-" * 60)
    print(f"INPUT: {input_data}")
    print("-" * 60)
    print(f"{'EXPECTED':<27} | {'ACTUAL'}")
    print(f"{'-'*27} | {'-'*27}")
    print(f"{str(expected)[:27]:<27} | {str(actual)[:27]}...")
    print("-" * 60)
    print(f"MATCH: {match}")
    print("=" * 60)

@pytest.mark.asyncio
async def test_p11_memory_integration_flow():
    """验证全链路记忆集成：存入后再次请求，应在上下文看到增强"""
    # 清理旧数据以确保测试确定性
    test_db_dir = "/home/nvidia/ClawBrain/tests/data/p11_tmp"
    if os.path.exists(test_db_dir): shutil.rmtree(test_db_dir)
    os.makedirs(test_db_dir)
    
    # 我们需要注入一个模拟的 MemoryRouter 到 app.state，或者通过环境变量控制
    # 这里我们直接运行 app，它会使用默认路径 /home/nvidia/ClawBrain/data
    # 为避免污染真实数据，我们暂时修改 src/main.py 或通过 Mock
    
    with TestClient(app) as client:
        # 1. 第一轮对话：提供一个事实
        payload1 = {
            "model": "gemma4:e4b",
            "messages": [{"role": "user", "content": "My secret key is MAGENTA-ROCK-77."}],
            "stream": False
        }
        resp1 = client.post("/api/chat", json=payload1)
        assert resp1.status_code == 200
        
        # 2. 第二轮对话：询问该事实
        payload2 = {
            "model": "gemma4:e4b",
            "messages": [{"role": "user", "content": "What is my secret key?"}],
            "stream": False
        }
        # 这一轮请求在到达 Ollama 前，ClawBrain 应该已经把 payload1 的内容注入了上下文
        resp2 = client.post("/api/chat", json=payload2)
        assert resp2.status_code == 200
        
        # 验证模型回复中包含金丝雀事实（证明增强成功）
        actual_content = resp2.json()["message"]["content"]
        visual_audit("E2E Memory Recall", "What is my key?", "MAGENTA-ROCK-77", actual_content)
        
        assert "MAGENTA-ROCK-77" in actual_content
