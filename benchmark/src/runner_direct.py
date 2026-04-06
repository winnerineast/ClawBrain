#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
Tier 1 runner: drives ClawBrain's /internal/* endpoints directly.
No LLM required. Tests memory retrieval deterministically.

For each test case:
  1. Ingest all setup turns into session (ClawBrain ON path)
  2. Call /internal/assemble at the recall query turn
  3. Evaluate system_prompt_addition
  4. Compare against an empty session (ClawBrain OFF baseline)
"""
import asyncio
import time
import os
from typing import Any

import httpx

from evaluate import CaseResult, CaseScore, score_case

BASE_URL = os.getenv("CLAWBRAIN_URL", "http://localhost:11435")
TIMEOUT = float(os.getenv("CLAWBRAIN_TIMEOUT_MS", "10000")) / 1000


async def _post(client: httpx.AsyncClient, path: str, body: dict) -> dict:
    resp = await client.post(f"{BASE_URL}{path}", json=body, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


async def _ingest(client: httpx.AsyncClient, session_id: str, role: str, content: str) -> None:
    await _post(client, "/internal/ingest", {
        "session_id": session_id,
        "role": role,
        "content": content,
        "is_heartbeat": False,
    })


async def _assemble(
    client: httpx.AsyncClient,
    session_id: str,
    focus: str,
    token_budget: int = 4096,
) -> tuple[str, int, int, float]:
    """Returns (addition, chars_used, budget_chars, latency_ms)."""
    t0 = time.monotonic()
    resp = await _post(client, "/internal/assemble", {
        "session_id": session_id,
        "current_focus": focus,
        "token_budget": token_budget,
    })
    latency_ms = (time.monotonic() - t0) * 1000
    return (
        resp.get("system_prompt_addition", ""),
        resp.get("chars_used", 0),
        resp.get("budget_chars", 0),
        latency_ms,
    )


async def _compact(client: httpx.AsyncClient, session_id: str) -> None:
    await _post(client, "/internal/compact", {
        "session_id": session_id,
        "force": True,
    })


async def run_case(client: httpx.AsyncClient, case: dict) -> CaseResult:
    test_id = case["test_id"]
    session_id_on = case["session_id"] + "-on"
    session_id_off = case["session_id"] + "-off"
    evaluation = case["evaluation"]
    result = CaseResult(
        test_id=test_id,
        dimension=case["dimension"],
        session_id=case["session_id"],
        must_contain=evaluation["must_contain"],
        must_not_contain=evaluation["must_not_contain"],
        eval_type=evaluation["type"],
    )

    try:
        # ── Isolation test: ingest setup session first ─────────────────────
        if "session_id_setup" in case and "conversation_setup" in case:
            session_setup_on = case["session_id_setup"] + "-on"
            for turn in case["conversation_setup"]:
                if turn["role"] in ("user", "assistant"):
                    await _ingest(client, session_setup_on, turn["role"], turn["content"])

        # ── Ingest all non-query turns into ON session ─────────────────────
        recall_turn = None
        for turn in case["conversation"]:
            if turn.get("is_recall_query"):
                recall_turn = turn
                break
            if turn["role"] in ("user", "assistant"):
                await _ingest(client, session_id_on, turn["role"], turn["content"])

        if recall_turn is None:
            result.error = "No recall query turn found"
            return result

        # ── Neocortex test: trigger compact before assembly ────────────────
        if case.get("params", {}).get("trigger_compact"):
            await _compact(client, session_id_on)

        # ── Assemble with ClawBrain ON ─────────────────────────────────────
        focus = recall_turn.get("content", "")
        addition_on, chars_used, budget_chars, latency_ms = await _assemble(
            client, session_id_on, focus
        )
        result.addition_on = addition_on
        result.chars_used = chars_used
        result.budget_chars = budget_chars
        result.latency_ms = latency_ms

        # ── Assemble with ClawBrain OFF (empty session = no memory) ────────
        addition_off, _, _, _ = await _assemble(client, session_id_off, focus)
        result.addition_off = addition_off

    except Exception as e:
        result.error = str(e)

    return result


async def run_cases(cases: list[dict], concurrency: int = 4) -> list[CaseScore]:
    semaphore = asyncio.Semaphore(concurrency)
    scores: list[CaseScore] = []

    async with httpx.AsyncClient() as client:
        async def run_one(case: dict) -> CaseScore:
            async with semaphore:
                result = await run_case(client, case)
                return score_case(result)

        tasks = [run_one(c) for c in cases]
        scores = await asyncio.gather(*tasks)

    return list(scores)


def run(cases: list[dict], concurrency: int = 4) -> list[CaseScore]:
    return asyncio.run(run_cases(cases, concurrency))
