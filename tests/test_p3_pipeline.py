# Generated from design/gateway.md v1.7
import pytest
import json
from pathlib import Path
from src.pipeline import WhitespaceCompressor, SafetyEnforcer, Pipeline
from src.models import StandardRequest, Message
from src.scout import ModelTier

def audit_log(test_name, input_data, expected, actual):
    # 根据 Rule 8 的长文本处理逻辑
    input_str = str(input_data)
    if len(input_str) > 200:
        display_input = f"{input_str[:100]} [...] {input_str[-100:]}"
    else:
        display_input = input_str

    print(f"\n[AUDIT START: {test_name}]")
    print(f"Input (Truncated if long): {display_input}")
    print(f"Expected (Summary): {expected}")
    print(f"Actual (Summary): {str(actual)[:200]}...")
    print("[AUDIT END]")

def test_real_world_wiki_compression():
    """使用真实 Wiki 数据测试压缩引擎的鲁棒性"""
    data_path = Path("tests/data/p3_real_world.json")
    data = json.loads(data_path.read_text())
    
    input_text = data["wiki_content"]
    actual = WhitespaceCompressor.compress(input_text)
    
    # 验证点 1：连续换行被压缩
    assert "\n\n\n" not in actual
    # 验证点 2：普通空格被压缩
    dirty_actual = WhitespaceCompressor.compress(data["dirty_content"])
    assert "    " not in dirty_actual
    
    audit_log("Wiki Long Text", input_text, "No triple newlines, single spaces", actual)

def test_real_world_code_protection():
    """验证在长篇技术文章中的代码块缩进被 100% 保护"""
    code_block = "def example_code():\n    if True:\n        print('indented')"
    input_text = f"Intro\n\n```python\n{code_block}\n```\n\nOutro"
    
    actual = WhitespaceCompressor.compress(input_text)
    
    audit_log("Code Protection", "Long text with code block", "Indentation preserved", actual)
    assert code_block in actual

@pytest.mark.asyncio
async def test_full_pipeline_real_world():
    """全链路测试：从 Pydantic Request 到经过 Pipeline 优化的输出"""
    req = StandardRequest(
        model="ollama/gemma4:31b",
        messages=[Message(role="system", content="Analyze this:    \n\n\nWiki Data")]
    )
    pipeline = Pipeline()
    optimized_req = pipeline.run(req, ModelTier.TIER_2)
    
    # 验证 1：内容已压缩
    assert "\n\n\n" not in optimized_req.messages[0].content
    # 验证 2：TIER 2 补丁已注入
    assert "[SYSTEM ENFORCEMENT]" in optimized_req.messages[0].content
    
    audit_log("Full Pipeline", "Raw Request", "Compressed + Patched Request", optimized_req.messages[0].content)
