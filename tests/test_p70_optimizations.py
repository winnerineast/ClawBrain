# Generated from design/memory_router.md v1.21
import pytest
import respx
import json
import re
import os
from httpx import Response
from src.memory.router import MemoryRouter
from src.memory.storage import clear_chroma_clients

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

def mock_embeddings(request):
    try:
        body = json.loads(request.content)
        inp = body.get("input", "")
        if isinstance(inp, list):
            num_embeddings = len(inp)
        else:
            num_embeddings = 1
    except Exception:
        num_embeddings = 1
    
    embeddings = [[0.1] * 768 for _ in range(num_embeddings)]
    data = [{"embedding": [0.1] * 768} for _ in range(num_embeddings)]
    return Response(200, json={"embeddings": embeddings, "data": data})

@pytest.mark.asyncio
@respx.mock
async def test_p70_late_stage_reranking(tmp_path):
    """Verify that late-stage filtering filters out irrelevant snippets while keeping relevant ones."""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()

    # Enable late-stage reranking explicitly
    router.enable_late_stage_reranking = True

    # Ingest mock embeddings
    respx.post(re.compile(r".*/api/embed|.*/v1/embeddings")).mock(side_effect=mock_embeddings)

    # Ingest two traces
    trace_id_relevant = await router.ingest(
        {"messages": [{"role": "user", "content": "Database config uses Postgres on port 5432"}]},
        session_id="session-rerank"
    )
    trace_id_noisy = await router.ingest(
        {"messages": [{"role": "user", "content": "UI theme is blue with dark mode"}]},
        session_id="session-rerank"
    )

    # Clear L1 working memory so we are testing L2 Hippocampus retrieval filtering
    router._get_wm("session-rerank").items = []

    # Mock Neocortex filter_relevant_snippets response to return index [0] (only candidate 0 is relevant)
    respx.post(re.compile(r".*/api/generate")).mock(return_value=Response(
        200, 
        json={"response": "[0]"}
    ))

    # Retrieve context
    context = await router.get_combined_context("session-rerank", "how do we configure the database?")

    visual_audit(
        "Late-Stage Reranking Relevance",
        "Context contains relevant technical database fact",
        True,
        "Database config uses Postgres" in context
    )
    visual_audit(
        "Late-Stage Reranking Noise Filtering",
        "Context filters out irrelevant UI blue theme noise",
        False,
        "UI theme is blue" in context
    )

    assert "Database config uses Postgres" in context
    assert "UI theme is blue" not in context
    await router.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_p70_query_expansion(tmp_path):
    """Verify that vague terms retrieve matching memories via query expansion."""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()

    # Enable query expansion explicitly
    router.enable_query_expansion = True
    router.enable_late_stage_reranking = True

    # Ingest mock embeddings
    respx.post(re.compile(r".*/api/embed|.*/v1/embeddings")).mock(side_effect=mock_embeddings)

    # Ingest technical trace
    await router.ingest(
        {"messages": [{"role": "user", "content": "PostgreSQL DB port is configured to 5432"}]},
        session_id="session-expansion"
    )

    # Clear L1 working memory so we query L2 database with expansion
    router._get_wm("session-expansion").items = []

    # First call: Query Expansion (synonyms list).
    # Second call: Late-stage snippet filtering (returning index [0]).
    route = respx.post(re.compile(r".*/api/generate"))
    route.side_effect = [
        Response(200, json={"response": '["SQL connection settings", "database port configuration"]'}),
        Response(200, json={"response": "[0]"})
    ]

    # Retrieve context using a vague query
    context = await router.get_combined_context("session-expansion", "setup db")

    visual_audit(
        "Query Expansion Recall",
        "Vague query retrieves specific PostgreSQL memory",
        True,
        "PostgreSQL DB port" in context
    )

    assert "PostgreSQL DB port" in context
    await router.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_p70_segmented_summaries(tmp_path):
    """Verify that summaries are segmented by session_id and room_id separately."""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()

    # Ingest mock embeddings
    respx.post(re.compile(r".*/api/embed|.*/v1/embeddings")).mock(side_effect=mock_embeddings)

    # Ingest trace in room "database"
    router._current_rooms["session-segmented"] = "database"
    respx.post(re.compile(r".*/api/generate")).mock(return_value=Response(
        200, 
        json={"response": "Technical Decisions: Use PostgreSQL 15."}
    ))
    await router.ingest(
        {"messages": [{"role": "user", "content": "PostgreSQL connection configured"}]},
        session_id="session-segmented",
        sync_distill=True
    )

    # Ingest trace in room "frontend"
    router._current_rooms["session-segmented"] = "frontend"
    respx.post(re.compile(r".*/api/generate")).mock(return_value=Response(
        200, 
        json={"response": "Technical Decisions: Use React UI."}
    ))
    await router.ingest(
        {"messages": [{"role": "user", "content": "React UI routing set up"}]},
        session_id="session-segmented",
        sync_distill=True
    )

    db_summary = router.neo.get_summary("session-segmented", room_id="database")
    fe_summary = router.neo.get_summary("session-segmented", room_id="frontend")

    visual_audit("Segmented Summary: Database Room", "Summary contains Postgres", True, "PostgreSQL" in (db_summary or ""))
    visual_audit("Segmented Summary: Frontend Room", "Summary contains React", True, "React" in (fe_summary or ""))

    assert "PostgreSQL" in (db_summary or "")
    assert "React" in (fe_summary or "")
    await router.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_p70_tiered_ingestion_archive(tmp_path):
    """Verify that low-value traces are written to the SQLite archive instead of ChromaDB."""
    clear_chroma_clients()
    router = MemoryRouter(db_dir=str(tmp_path))
    await router.wait_until_ready()

    # Ingest mock embeddings
    respx.post(re.compile(r".*/api/embed|.*/v1/embeddings")).mock(side_effect=mock_embeddings)

    # Mock L6b score response to return 0.2 (low value trace)
    respx.post(re.compile(r".*/api/generate")).mock(return_value=Response(
        200, 
        json={"response": "0.2"}
    ))

    trace_id = await router.ingest(
        {"messages": [{"role": "user", "content": "hi how are you"}]},
        session_id="session-archive"
    )

    # Check that trace is NOT in ChromaDB active collection
    chroma_res = router.hippo.traces_col.get(ids=[trace_id])
    is_in_chroma = len(chroma_res["ids"]) > 0

    # Check that trace IS in SQLite archive database
    archived = router.hippo.get_archived_traces("session-archive")
    is_in_sqlite = any(t["trace_id"] == trace_id for t in archived)

    visual_audit("L6b Archive: Absent from ChromaDB", "Low value trace not indexed in ChromaDB", False, is_in_chroma)
    visual_audit("L6b Archive: Present in SQLite", "Low value trace stored in SQLite archived_traces table", True, is_in_sqlite)

    assert not is_in_chroma
    assert is_in_sqlite
    await router.aclose()
