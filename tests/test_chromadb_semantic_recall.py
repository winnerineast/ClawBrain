import pytest
import os
import shutil
from src.memory.storage import Hippocampus

TEST_DATA_DIR = "tests/data/chroma_semantic_tmp"

def test_semantic_recall_vs_keyword():
    """
    PROVING SEMANTIC RECALL:
    This test verifies that ChromaDB can retrieve a fact based on meaning
    even when the query shares NO keywords with the original fact.
    """
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)
    
    hp = Hippocampus(db_dir=TEST_DATA_DIR)
    session_id = "semantic-demo"
    
    # 1. Plant a fact with specific terminology
    fact = "The primary data store is located at 192.168.1.50"
    hp.save_trace(
        trace_id="fact-001",
        payload={"stimulus": {"content": fact}, "model": "test-model"},
        search_text=fact,
        session_id=session_id
    )
    
    # 2. Query using DIFFERENT words but SAME meaning
    # "database" is not in "data store"
    # "address" is not in the fact
    query = "What is the database address?"
    
    results = hp.search(query, session_id=session_id)
    
    print(f"\n[SEMANTIC TEST] Query: '{query}'")
    print(f"[SEMANTIC TEST] Fact:  '{fact}'")
    print(f"[SEMANTIC TEST] Results: {results}")
    
    # PROOF: In keyword FTS5, this would return [] because 'database' and 'address' don't match.
    # In ChromaDB (Semantic), it should find 'fact-001'.
    assert "fact-001" in results, f"Failed to semantically recall fact. Results: {results}"
    assert results[0] == "fact-001", "The semantic match should be the top result."

def test_strict_session_isolation():
    """
    Ensures that semantic similarity does NOT leak across sessions.
    """
    hp = Hippocampus(db_dir=TEST_DATA_DIR)
    
    # Session A fact
    hp.save_trace(
        trace_id="session-a-fact",
        payload={"stimulus": {"content": "The secret key is 'ALICE-123'"}, "model": "test-model"},
        search_text="The secret key is 'ALICE-123'",
        session_id="session-alice"
    )
    
    # Query from Session B for something similar
    results = hp.search("What is the secret key?", session_id="session-bob")
    
    print(f"\n[ISOLATION TEST] Query from Session Bob: 'What is the secret key?'")
    print(f"[ISOLATION TEST] Results: {results}")
    
    # PROOF: Even though the query is semantically identical to Session A's fact,
    # it must NOT be returned in Session B.
    assert "session-a-fact" not in results, "SECURITY BREACH: Semantic leakage between sessions!"

def test_comprehensive_semantic_matrix():
    """
    PROVING 100% SUCCESS CLAIM:
    Verifies that ChromaDB can retrieve a fact based on meaning
    across a diverse semantic matrix with zero keyword overlap.
    """
    hp = Hippocampus(db_dir=TEST_DATA_DIR)
    session_id = "semantic-matrix"
    
    # Define 10 distinct semantic pairs (zero keyword overlap)
    matrix = [
        # Performance
        {"fact": "The system latency is 10ms.", "query": "speed"},
        # Security
        {"fact": "AES-256 encryption is enabled.", "query": "protection"},
        # Persistence
        {"fact": "Data survives after a hard reboot.", "query": "save"},
        # Pricing
        {"fact": "The service costs five dollars monthly.", "query": "expense"},
        # Location
        {"fact": "The server farm is in Frankfurt.", "query": "where"},
        # Color
        {"fact": "The button is painted azure.", "query": "hue"},
        # Schedule
        {"fact": "The meeting starts at high noon.", "query": "time"},
        # Capacity
        {"fact": "The drive holds two terabytes.", "query": "size"},
        # Access
        {"fact": "Only the administrator can view this.", "query": "permissions"},
        # Status
        {"fact": "The task finished without issues.", "query": "result"}
    ]
    
    # 1. Plant all facts
    for i, pair in enumerate(matrix):
        trace_id = f"fact-matrix-{i}"
        hp.save_trace(
            trace_id=trace_id,
            payload={"stimulus": {"content": pair["fact"]}, "model": "test-model"},
            search_text=pair["fact"],
            session_id=session_id
        )
    
    import time
    time.sleep(0.5)

    # 2. Query each and assert #1 result
    success_count = 0
    for i, pair in enumerate(matrix):
        expected_trace_id = f"fact-matrix-{i}"
        results = hp.search(pair["query"], session_id=session_id)
        
        assert len(results) > 0, f"Query '{pair['query']}' returned no results."
        assert results[0] == expected_trace_id, f"Query '{pair['query']}' failed to retrieve '{pair['fact']}' as #1. Got {results}"
        success_count += 1
        
    assert success_count == 10, "Failed to achieve 100% semantic recall across the matrix."

if __name__ == "__main__":
    # For manual execution
    try:
        test_semantic_recall_vs_keyword()
        test_strict_session_isolation()
        print("\n✅ PROOF COMPLETE: Semantic recall and Session Isolation verified.")
    except Exception as e:
        print(f"\n❌ PROOF FAILED: {e}")
