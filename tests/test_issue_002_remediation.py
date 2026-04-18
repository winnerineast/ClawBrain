# Generated for Phase 29/30/31 Remediation Verification
import pytest
import os
import shutil
import asyncio
import json
from src.memory.router import MemoryRouter
from src.memory.storage import Hippocampus, clear_chroma_clients
from src.memory.neocortex import Neocortex

@pytest.mark.asyncio
async def test_phase_29_neocortex_silence(tmp_path):
    """Verify that no L3 header or text is injected if summary is missing."""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()
    
    # Context with NO memory at all
    context = await router.get_combined_context("session_empty", "some focus")
    assert context == ""
    assert "NEOCORTEX" not in context
    assert "No historical summary." not in context

@pytest.mark.asyncio
async def test_phase_29_neocortex_presence(tmp_path):
    """Verify that L3 header IS injected if summary exists."""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()
    router.neo._save_summary("session_l3", "This is a summary.")
    
    context = await router.get_combined_context("session_l3", "some focus")
    assert "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===" in context
    assert "This is a summary." in context

@pytest.mark.asyncio
async def test_phase_30_plain_text_hippocampus(tmp_path):
    """Verify that L2 memories are injected as plain text bullet points, not JSON."""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()
    
    # Ingest a trace
    msg_content = "Python is a programming language."
    await router.ingest({
        "messages": [
            {"role": "user", "content": "Tell me about Python."},
            {"role": "assistant", "content": msg_content}
        ]
    }, session_id="session_l2")
    
    context = await router.get_combined_context("session_l2", "Python")
    
    assert "=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===" in context
    # Should NOT contain JSON braces
    assert '{"role":' not in context
    # Should contain formatted text: role: content
    assert "user: Tell me about Python." in context
    assert "assistant: Python is a programming language." in context

@pytest.mark.asyncio
async def test_combined_layers_formatting(tmp_path):
    """Verify headers and spacing when multiple layers are present."""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()
    
    # L3
    router.neo._save_summary("session_multi", "L3 Summary Content")
    
    # L2
    await router.ingest({
        "messages": [{"role": "user", "content": "L2 Memory Content"}]
    }, session_id="session_multi")
    
    # L1 (already updated by ingest above)
    
    context = await router.get_combined_context("session_multi", "Memory Content")
    
    assert "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===" in context
    assert "=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===" in context
    assert "=== ACTIVE CONVERSATION (WORKING MEMORY) ===" in context
    
    # Check for separation (at least one newline between sections)
    assert "\n\n" in context

@pytest.mark.asyncio
async def test_phase_31_priority_order(tmp_path):
    """Verify that L1 (Working Memory) is prioritized over L2 (Hippocampus) when budget is tight."""
    clear_chroma_clients()
    
    # --- STACK MATH DERIVATION FOR BUDGET (250) ---
    # 1. Outer Wrapper: [CLAWBRAIN MEMORY]...[END...]  -> ~50 chars
    # 2. L3 (Neocortex): Header(45) + Msg(35) -> 80 chars
    # 3. L1 (WM): Header(48) + Msg(35)        -> 83 chars
    # Sum for L3 + L1 = 50 + 80 + 83 = 213 chars.
    # Remaining budget = 250 - 213 = 37 chars.
    # L2 Header alone is > 40 chars, so L2 is guaranteed to be excluded.
    os.environ["CLAWBRAIN_MAX_CONTEXT_CHARS"] = "250"
    
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()
    
    # 1. Add L3 (High priority) - ~50 chars
    router.neo._save_summary("session_priority", "L3 Fact: User prefers Rust over C++.")
    
    # 2. Add L1 Content via ingest - ~50 chars
    await router.ingest({
        "messages": [{"role": "user", "content": "Active conversational turn content."}]
    }, session_id="session_priority")
    
    # 3. Add a different L2 trace that matches focus - ~50 chars
    router.hippo.save_trace("tid_old", {"stimulus": {"messages": [{"role": "user", "content": "Old historical snippet content."}]}}, search_text="priority_focus", session_id="session_priority")
    
    context = await router.get_combined_context("session_priority", "priority_focus")
    
    print(f"\nPRIORITY TEST CONTEXT (Budget 250):\n{context}")
    
    assert "=== SYSTEM MEMORY SUMMARY (NEOCORTEX) ===" in context
    assert "=== ACTIVE CONVERSATION (WORKING MEMORY) ===" in context
    
    # L2 should be absent because budget is exhausted by L3 and L1
    assert "=== RELEVANT HISTORICAL SNIPPETS (HIPPOCAMPUS) ===" not in context
    
    if "CLAWBRAIN_MAX_CONTEXT_CHARS" in os.environ:
        del os.environ["CLAWBRAIN_MAX_CONTEXT_CHARS"]
