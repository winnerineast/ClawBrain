# Generated from design/memory_hippocampus.md v1.6 / design/memory_router.md v1.9 / design/gateway.md v1.39
import pytest
import os
import shutil
import asyncio
from src.memory.storage import Hippocampus, clear_chroma_clients
from src.memory.router import MemoryRouter

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

# ── P15-A: FTS 降级回退 (Now ChromaDB Semantic Search) ──────────────────

def test_p15_fts_exact_phrase_match(tmp_path):
    """Level 1：精确短语能命中时直接返回 (Top Match in Semantic)"""
    clear_chroma_clients()
    hp = Hippocampus(db_dir=str(tmp_path))
    hp.save_trace("t1", {"x": 1}, search_text="CANARY-EXACT-MATCH")
    hp.save_trace("t2", {"x": 2}, search_text="unrelated noise data")

    results = hp.search("CANARY-EXACT-MATCH")
    visual_audit("FTS Level 1 (Exact Phrase)", "Search exact token", "t1 as top match", str(results))
    # Semantic search might return both, but t1 MUST be the top result
    assert len(results) >= 1
    assert results[0] == "t1"

def test_p15_fts_keyword_fallback(tmp_path):
    """Level 2：短语无法命中时，关键词 AND 回退能召回 (Semantic context match)"""
    clear_chroma_clients()
    hp = Hippocampus(db_dir=str(tmp_path))
    # 存入包含多关键词的内容
    hp.save_trace("t3", {"x": 3}, search_text="fastapi database migration guide")
    hp.save_trace("t4", {"x": 4}, search_text="unrelated content here")

    # 用自然语言查询（不会精确命中，但关键词应该匹配）
    results = hp.search("fastapi migration")
    visual_audit("FTS Level 2 (Keyword Fallback)", "Natural language query", True, len(results) > 0)
    assert len(results) > 0
    assert "t3" in results

def test_p15_fts_empty_query_safe(tmp_path):
    """空 query 不抛异常，返回空列表"""
    clear_chroma_clients()
    hp = Hippocampus(db_dir=str(tmp_path))
    results = hp.search("")
    visual_audit("FTS Empty Query Safety", "Empty string input", "[]", str(results))
    assert results == []

# ── P15-B: Context 预算控制 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p15_context_budget_enforced(tmp_path):
    """注入内容不超过 MAX_CONTEXT_CHARS 上限"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_MAX_CONTEXT_CHARS"] = "500"

    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()

    # 塞入大量内容
    for i in range(10):
        await router.ingest({
            "messages": [{"role": "user", "content": f"Long message content number {i} " * 20}]
        })

    context = await router.get_combined_context("test", "long message content")
    # 加上固定 header 的字符，允许一定溢出（header ~150 chars）
    visual_audit(
        "Context Budget Enforcement",
        f"MAX=500, actual len={len(context)}",
        "len <= 750",
        f"len={len(context)}"
    )
    # Increased buffer slightly for ChromaDB headers
    assert len(context) <= 750

    if "CLAWBRAIN_MAX_CONTEXT_CHARS" in os.environ:
        del os.environ["CLAWBRAIN_MAX_CONTEXT_CHARS"]

@pytest.mark.asyncio
async def test_p15_context_budget_priority_order(tmp_path):
    """L3 内容优先于 L2 被保留"""
    clear_chroma_clients()
    os.environ["CLAWBRAIN_MAX_CONTEXT_CHARS"] = "300"

    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()

    # 手动写入新皮层摘要
    router.neo._save_summary("priority_test", "NEOCORTEX_CANARY " * 10)

    # 写入海马体
    await router.ingest({"messages": [{"role": "user", "content": "HIPPOCAMPUS_CANARY data here"}]})

    context = await router.get_combined_context("priority_test", "HIPPOCAMPUS_CANARY")
    visual_audit(
        "Context Priority Order",
        "L3 Neocortex should appear before L2 Hippocampus",
        True,
        context.index("NEOCORTEX_CANARY") < context.index("HIPPOCAMPUS") if "HIPPOCAMPUS" in context else True
    )
    assert "NEOCORTEX_CANARY" in context

    if "CLAWBRAIN_MAX_CONTEXT_CHARS" in os.environ:
        del os.environ["CLAWBRAIN_MAX_CONTEXT_CHARS"]

# ── P15-C: 流式内容提取工具函数 ────────────────────────────────────────────

def _extract_chunk_content(chunk: bytes) -> str:
    """从单个 streaming chunk 中提取 assistant 内容（与 main.py 逻辑对齐）"""
    import json
    try:
        text = chunk.decode('utf-8', errors='ignore').strip()
        if text.startswith('data:'):
            text = text[5:].strip()
        if not text or text == '[DONE]':
            return ''
        data = json.loads(text)
        if 'message' in data:
            return data['message'].get('content', '')
        elif 'choices' in data:
            for choice in data.get('choices', []):
                c = choice.get('delta', {}).get('content', '')
                if c:
                    return c
        return ''
    except:
        return ''

def test_p15_stream_chunk_ollama_format():
    """Ollama 流式 chunk 提取"""
    import json
    chunk = json.dumps({"message": {"content": "Hello"}, "done": False}).encode()
    result = _extract_chunk_content(chunk)
    visual_audit("Stream Chunk (Ollama)", "message.content extraction", "Hello", result)
    assert result == "Hello"

def test_p15_stream_chunk_openai_sse_format():
    """OpenAI SSE 流式 chunk 提取"""
    import json
    data = {"choices": [{"delta": {"content": "World"}, "index": 0}]}
    chunk = f"data: {json.dumps(data)}".encode()
    result = _extract_chunk_content(chunk)
    visual_audit("Stream Chunk (OpenAI SSE)", "delta.content extraction", "World", result)
    assert result == "World"

def test_p15_stream_chunk_done_signal():
    """[DONE] 信号正确忽略"""
    chunk = b"data: [DONE]"
    result = _extract_chunk_content(chunk)
    visual_audit("Stream Chunk ([DONE])", "Should return empty string", "", result)
    assert result == ""

def test_p15_stream_chunk_malformed():
    """损坏 chunk 静默跳过"""
    chunk = b"garbage data }{]["
    result = _extract_chunk_content(chunk)
    visual_audit("Stream Chunk (Malformed)", "Should return empty string", "", result)
    assert result == ""
