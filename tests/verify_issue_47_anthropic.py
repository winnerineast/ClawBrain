# Generated for Issue #47 Verification
import pytest
import json
import asyncio
import respx
from httpx import Response
from fastapi.testclient import TestClient
from src.main import app, EngineState
from src.gateway.registry import ProviderConfig
from src.pipeline import Pipeline
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_anthropic_sse_translation():
    """
    验证 ClawBrain 能够将 Anthropic 的流式输出 (SSE) 转换为 OpenAI 格式。
    """
    # 模拟必要的应用状态
    app.state.engine_state = EngineState.READY
    app.state.memory_router = AsyncMock()
    app.state.memory_router.pre_turn_pending = AsyncMock(return_value="test-trace-id")
    app.state.memory_router.get_combined_context = AsyncMock(return_value="[CLAWBRAIN MEMORY] Some facts...")
    
    # 模拟注册表返回 Anthropic 配置
    app.state.registry = MagicMock()
    anthropic_config = ProviderConfig(name="anthropic", base_url="https://api.anthropic.com", protocol="anthropic")
    app.state.registry.resolve_provider.return_value = ("anthropic", anthropic_config)
    
    # 模拟 scout 组件
    app.state.scout = AsyncMock()
    app.state.scout.get_model_tier.return_value = 2
    
    # 使用真实的 Pipeline 对象来测试内部的流转换逻辑
    app.state.pipeline = Pipeline()
    import httpx
    app.state.http_client = httpx.AsyncClient()
    
    # 模拟 Anthropic 的原始流数据
    anthropic_chunks = [
        'data: {"type": "message_start", "message": {"id": "msg_1", "role": "assistant", "content": [], "model": "claude-3"}}',
        'data: {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}',
        'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}',
        'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " World"}}',
        'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": null}}',
        'data: {"type": "message_stop"}'
    ]
    
    stream_content = "\n\n".join(anthropic_chunks).encode() + b"\n\n"

    async with respx.mock:
        # 模拟上游 Anthropic 接口
        respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(
            200, 
            content=stream_content,
            headers={"Content-Type": "text/event-stream"}
        ))

        # 使用 FastAPI TestClient 调用 ClawBrain
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 构造请求，强制使用 Anthropic 协议
            payload = {
                "model": "anthropic/claude-3",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True
            }
            
            response = await ac.post("/v1/messages", json=payload)
            assert response.status_code == 200
            
            collected_text = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    data = json.loads(data_str)
                    if "choices" in data and data["choices"]:
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            collected_text += delta["content"]

            print(f"\n[ISSUE-47 AUDIT] Collected Text: '{collected_text}'")
            assert collected_text == "Hello World"

if __name__ == "__main__":
    asyncio.run(test_anthropic_sse_translation())
