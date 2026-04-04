# Generated from design/gateway.md v1.9
import pytest
import json
from pathlib import Path
from src.pipeline import WhitespaceCompressor, SafetyEnforcer, Pipeline
from src.models import StandardRequest, Message
from src.scout import ModelTier

def audit_log(test_name, input_data, expected, actual):
    # 根据 Rule 8 的审计规范
    print(f"\n[AUDIT START: {test_name}]")
    print(f"Input: {repr(input_data)}")
    print(f"Expected: {repr(expected)}")
    print(f"Actual:   {repr(actual)}")
    print("[AUDIT END]")

def test_real_world_wiki_compression():
    """使用真实 Wiki 数据测试压缩引擎"""
    data_path = Path("tests/data/p3_real_world.json")
    data = json.loads(data_path.read_text())
    input_text = data["wiki_content"]
    actual = WhitespaceCompressor.compress(input_text)
    
    # 基础特征验证
    assert "\n\n\n" not in actual
    audit_log("Wiki Long Text Feature Check", "Long Wiki Content", "No triple newlines", "PASSED")

def test_real_world_code_protection():
    """验证代码块缩进 100% 保护 (精确比对)"""
    code_block = "def example_code():\n    if True:\n        print('indented code block')"
    input_text = f"Header\n\n```python\n{code_block}\n```\n\nFooter"
    
    actual = WhitespaceCompressor.compress(input_text)
    
    # 精确验证代码块内容是否原封不动
    audit_log("Exact Code Block Protection", code_block, code_block, actual)
    assert code_block in actual

@pytest.mark.asyncio
async def test_full_pipeline_precision():
    """全链路精确匹配测试 (核心升级点)"""
    # 故意设计一个复杂的、带多余空格和换行的输入
    raw_content = "Task:    Run\n\n\nResult: OK"
    # 期望结果计算：
    # 1. 'Task:    Run' -> 'Task: Run' (4空格变1个)
    # 2. '\n\n\n' -> '\n\n' (3换行变2个)
    # 3. 注入 TIER 2 补丁
    expected_content = "Task: Run\n\nResult: OK" + SafetyEnforcer.TIER2_PATCH
    
    req = StandardRequest(
        model="ollama/gemma4:31b",
        messages=[Message(role="system", content=raw_content)]
    )
    
    pipeline = Pipeline()
    optimized_req = pipeline.run(req, ModelTier.TIER_2)
    actual_content = optimized_req.messages[0].content
    
    audit_log("Full Pipeline Precision Match", raw_content, expected_content, actual_content)
    
    # 升级为逐字符精确匹配
    assert actual_content == expected_content
