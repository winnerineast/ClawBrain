#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
Tier 1 runner: drives ClawBrain's /v1/* endpoints directly.
No LLM required. Tests memory retrieval deterministically.

For each test case:
  1. Ingest all setup turns into session (ClawBrain ON path)
  2. Call /v1/query at the recall query turn
  3. Evaluate the retrieved context against expected_output
  4. Compare against an empty session (ClawBrain OFF baseline)
"""
import asyncio
import time
import os
from typing import Any

import httpx

from evaluate import CaseResult, CaseScore, score_case

BASE_URL = os.getenv("CLAWBRAIN_URL", "http://localhost:11435")
TIMEOUT = float(os.getenv("CLAWBRAIN_TIMEOUT_MS", "60000")) / 1000


async def _post(client: httpx.AsyncClient, path: str, body: dict) -> dict:
    resp = await client.post(f"{BASE_URL}{path}", json=body, timeout=TIMEOUT)
    if resp.status_code != 200:
        print(f"ERROR: {path} returned {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    return resp.json()


async def _ingest(client: httpx.AsyncClient, session_id: str, content: str) -> None:
    await _post(client, "/v1/ingest", {
        "session_id": session_id,
        "content": content,
    })


async def _query(
    client: httpx.AsyncClient,
    session_id: str,
    query_text: str,
    budget: int = 4000,
) -> tuple[str, float]:
    """Returns (context_text, latency_ms)."""
    t0 = time.monotonic()
    resp_json = await _post(client, "/v1/query", {
        "session_id": session_id,
        "query": query_text,
        "budget": budget,
    })
    latency_ms = (time.monotonic() - t0) * 1000
    return resp_json.get("context", ""), latency_ms


async def _compact(client: httpx.AsyncClient, session_id: str) -> None:
    # Use the manual distill endpoint to simulate compaction for benchmark
    await _post(client, f"/v1/memory/{session_id}/distill", {})
    # Wait a bit for background task
    await asyncio.sleep(2)


async def run_case(client: httpx.AsyncClient, case: dict) -> CaseResult:
    test_id = case["test_id"]
    session_id_on = case["session_id"] + "-on"
    session_id_off = case["session_id"] + "-off"
    evaluation = case["evaluation"]
    
    result = CaseResult(
        test_id=test_id,
        dimension=case["dimension"],
        session_id=case["session_id"],
        expected_output=evaluation["expected_output"],
        must_contain=evaluation["must_contain"],
        must_not_contain=evaluation["must_not_contain"],
        eval_type=evaluation["type"],
    )

    try:
        # ── Isolation test: ingest setup session first ─────────────────────
        if "session_id_setup" in case and "conversation_setup" in case:
            session_setup_on = case["session_id_setup"] + "-on"
            for turn in case["conversation_setup"]:
                if turn["role"] == "user":
                    await _ingest(client, session_setup_on, turn["content"])
        
        # ── Ingest all non-query turns into ON session ─────────────────────
        recall_turn = None
        for turn in case["conversation"]:
            if turn.get("is_recall_query") == True:
                recall_turn = turn
                break
            if turn.get("role") == "user":
                await _ingest(client, session_id_on, turn["content"])

        if recall_turn is None:
            result.error = "No recall query turn found"
            return result

        # ── Neocortex test: trigger compact before query ───────────────────
        if case.get("params", {}).get("trigger_compact"):
            await _compact(client, session_id_on)

        # ── Query with ClawBrain ON ────────────────────────────────────────
        focus = recall_turn.get("content", "")
        context_on, latency_ms = await _query(client, session_id_on, focus)
        result.addition_on = context_on
        result.latency_ms = latency_ms

        # ── Query with ClawBrain OFF (stateless baseline = no memory) ──────
        # We DO NOT call /v1/query here because that is a ClawBrain-only feature.
        # A standard LLM without ClawBrain would have an empty prompt addition.
        result.addition_off = ""

    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)}"

    return result


async def run_cases(cases: list[dict], concurrency: int = 1) -> list[CaseScore]:
    semaphore = asyncio.Semaphore(concurrency)
    total = len(cases)
    print(f"\n[TIER 1] Starting execution of {total} cases...")
    
    async with httpx.AsyncClient() as client:
        async def run_one(idx: int, case: dict) -> CaseScore:
            async with semaphore:
                # Heartbeat: [001/159] Running test_id... (Must be inside semaphore)
                print(f"[{idx+1:03d}/{total:03d}] Running {case['test_id']}... ", end="", flush=True)
                try:
                    result = await run_case(client, case)
                    score = score_case(result)
                    status = "✅ PASS" if score.recall_on > 0 else "❌ FAIL"
                    if score.error: status = f"⚠️ ERROR: {score.error[:20]}"
                    print(status, flush=True)
                    return score
                except Exception as e:
                    print(f"💥 CRASH: {str(e)[:30]}", flush=True)
                    return CaseScore(test_id=case['test_id'], dimension=case['dimension'], error=str(e))

        tasks = [run_one(i, c) for i, c in enumerate(cases)]
        scores = await asyncio.gather(*tasks)

    return list(scores)


def run(cases: list[dict], concurrency: int = 1) -> list[CaseScore]:
    return asyncio.run(run_cases(cases, concurrency))
