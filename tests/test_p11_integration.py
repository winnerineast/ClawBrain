# Generated from design/memory_integration.md v1.4
import pytest
import json
import os
import shutil
import time
from fastapi.testclient import TestClient
from src.main import app

TEST_DB_DIR = "/home/nvidia/ClawBrain/tests/data/p11_real_tmp"

def visual_audit_memory(test_name, round_num, input_data, expected_recall, actual_payload):
    print(f"\n[REAL E2E AUDIT: {test_name} - Round {round_num}]")
    print("=" * 80)
    print(f"INPUT: {input_data}")
    print("-" * 80)
    print(f"{'EXPECTED RECALL':<38} | {'ACTUAL ENHANCEMENT'}")
    
    actual_snippet = str(actual_payload)[:100].replace('\n', ' ')
    print(f"{expected_recall:<38} | {actual_snippet}")
    print("-" * 80)
    print(f"MEMORY ECHO MATCH: {'YES' if expected_recall.lower() in str(actual_payload).lower() else 'NO'}")
    print("=" * 80)

@pytest.mark.asyncio
async def test_p11_full_chain_memory_echo_real():
    """Phase 11 真实环境集成验收：验证在真实 Ollama 环境下的记忆回响"""
    if os.path.exists(TEST_DB_DIR): shutil.rmtree(TEST_DB_DIR)
    os.makedirs(TEST_DB_DIR)
    
    # 3.1 准则：通过环境变量强制隔离数据库路径
    os.environ["CLAWBRAIN_DB_DIR"] = TEST_DB_DIR
    
    # 只有在 TestClient 启动时，Lifespan 才会读取环境变量
    with TestClient(app) as client:
        # Round 1: 存入秘密 (向真实的 Ollama 发送请求)
        # 注意：此处必须使用您本地确实存在的模型名，否则后端依然会报 404
        # 根据日志，您使用的是 gemma4:e4b，我将去掉 ollama/ 前缀以对齐原生协议
        payload1 = {
            "model": "gemma4:e4b",
            "messages": [{"role": "user", "content": "The secret code is APPLE-777"}]
        }
        client.post("/api/chat", json=payload1)
        
        # 强制等待一小会儿确保异步存证完成
        time.sleep(1.0)
        
        # Round 2: 验证召回
        # 我们模拟网关内部合成逻辑
        memory = client.app.state.memory_router
        enhanced_context = await memory.get_combined_context("default", "secret code")
        
        visual_audit_memory(
            "Real Environment Echo",
            2,
            "Recall secret code",
            "APPLE-777",
            enhanced_context
        )
        
        assert "APPLE-777" in enhanced_context
        assert "WORKING MEMORY" in enhanced_context
