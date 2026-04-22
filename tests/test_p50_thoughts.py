import pytest
import os
import json
from src.memory.storage import Hippocampus, clear_chroma_clients

def test_p50_thoughts_lifecycle(tmp_path):
    """v0.2: Verify thoughts storage, retrieval, and root source mapping."""
    clear_chroma_clients()
    hp = Hippocampus(db_dir=str(tmp_path))
    session_id = "test-session"
    
    # 1. Seed some raw traces (Root Sources)
    trace_id_1 = "trace-1"
    trace_id_2 = "trace-2"
    hp.save_trace(trace_id_1, {"stimulus": {"messages": [{"role": "user", "content": "I love Python"}]}}, 
                  search_text="user loves python", session_id=session_id)
    hp.save_trace(trace_id_2, {"stimulus": {"messages": [{"role": "user", "content": "I hate Java"}]}}, 
                  search_text="user hates java", session_id=session_id)
    
    # 2. Store a high-level thought mapped to these traces
    thought_text = "The user prefers dynamic languages like Python over verbose ones like Java."
    source_traces = [trace_id_1, trace_id_2]
    hp.upsert_thought(session_id, thought_text, source_traces, confidence=0.95)
    
    # 3. Search for the thought
    results = hp.search_thoughts("What languages does the user like?", session_id)
    assert len(results) > 0
    assert results[0]["thought"] == thought_text
    assert results[0]["source_traces"] == source_traces
    assert results[0]["confidence"] == 0.95
    
    # 4. Resolve Root Sources
    resolved_traces = hp.get_traces_by_ids(results[0]["source_traces"])
    assert len(resolved_traces) == 2
    
    def get_user_msg(t):
        msgs = t["payload"].get("stimulus", {}).get("messages", [])
        return msgs[0]["content"] if msgs else ""

    user_contents = [get_user_msg(t) for t in resolved_traces]
    print(f"\n[DEBUG] Resolved user contents: {user_contents}")
    assert any("I love Python" in c for c in user_contents)
    assert any("I hate Java" in c for c in user_contents)

def test_p50_thoughts_session_isolation(tmp_path):
    """v0.2: Thoughts should be isolated by session_id."""
    clear_chroma_clients()
    hp = Hippocampus(db_dir=str(tmp_path))
    
    hp.upsert_thought("alice", "Alice likes apples", ["t1"])
    hp.upsert_thought("bob", "Bob likes bananas", ["t2"])
    
    alice_results = hp.search_thoughts("fruit", "alice")
    bob_results = hp.search_thoughts("fruit", "bob")
    
    assert len(alice_results) == 1
    assert "Alice" in alice_results[0]["thought"]
    assert len(bob_results) == 1
    assert "Bob" in bob_results[0]["thought"]
