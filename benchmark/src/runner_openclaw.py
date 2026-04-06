#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
Tier 2 runner: drives the full OpenClaw CLI pipeline.
Requires: openclaw installed, local LLM (Ollama), ClawBrain server running.

Each message is sent via:
  openclaw --profile benchmark-{on|off} agent --local --json
            --session-id <id> --message <content>

The model's response text is evaluated against must_contain patterns.
"""
import json
import re
import subprocess
import time
import os
from typing import Any

from evaluate import CaseResult, CaseScore, score_case

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
OPENCLAW_TIMEOUT = int(os.getenv("OPENCLAW_TURN_TIMEOUT", "120"))  # seconds per turn


def _run_turn(
    profile: str,
    session_id: str,
    message: str,
) -> tuple[str, float]:
    """
    Send one message via openclaw agent --local --json.
    Returns (response_text, latency_ms).
    Raises on non-zero exit or JSON parse failure.
    """
    cmd = [
        OPENCLAW_BIN,
        "--profile", profile,
        "agent",
        "--local",
        "--json",
        "--session-id", session_id,
        "--message", message,
    ]
    t0 = time.monotonic()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=OPENCLAW_TIMEOUT,
    )
    latency_ms = (time.monotonic() - t0) * 1000

    # openclaw writes JSON output to stderr; stdout is always empty
    output = proc.stderr

    if proc.returncode != 0:
        raise RuntimeError(
            f"openclaw exited {proc.returncode}: {output[:500]}"
        )

    # Strip ANSI colour codes before parsing JSON
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    clean = ansi_escape.sub('', output)
    match = re.search(r'(\{.*)', clean, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in stderr: {clean[:300]}")

    data = json.loads(match.group(1))
    payloads = data.get("payloads", [])
    text = " ".join(p.get("text", "") for p in payloads if p.get("text"))
    return text, latency_ms


def _run_conversation(
    profile: str,
    session_id: str,
    conversation: list[dict],
) -> tuple[str, float]:
    """
    Play through all turns. Returns (recall_response_text, latency_ms).
    Only user turns are sent (assistant turns are the model's output).
    Returns the response to the first is_recall_query turn.
    """
    recall_text = ""
    recall_latency = 0.0

    for turn in conversation:
        if turn["role"] != "user":
            continue
        text, lat = _run_turn(profile, session_id, turn["content"])
        if turn.get("is_recall_query"):
            recall_text = text
            recall_latency = lat
            break  # stop after recall query

    return recall_text, recall_latency


def run_case(case: dict) -> CaseResult:
    test_id = case["test_id"]
    session_on  = case["session_id"] + "-t2-on"
    session_off = case["session_id"] + "-t2-off"
    evaluation  = case["evaluation"]

    result = CaseResult(
        test_id=test_id,
        dimension=case["dimension"],
        session_id=case["session_id"],
        must_contain=evaluation["must_contain"],
        must_not_contain=evaluation["must_not_contain"],
        eval_type=evaluation["type"],
    )

    try:
        # ── ClawBrain ON ──────────────────────────���───────────────────────
        # Setup session (if isolation test)
        if "session_id_setup" in case and "conversation_setup" in case:
            setup_session_on = case["session_id_setup"] + "-t2-on"
            for turn in case["conversation_setup"]:
                if turn["role"] == "user":
                    _run_turn("benchmark-on", setup_session_on, turn["content"])

        resp_on, lat_on = _run_conversation(
            "benchmark-on", session_on, case["conversation"]
        )
        result.response_on = resp_on
        result.latency_ms_t2 = lat_on

        # ── ClawBrain OFF (legacy engine) ─────────────────────────────────
        resp_off, _ = _run_conversation(
            "benchmark-off", session_off, case["conversation"]
        )
        result.response_off = resp_off

    except subprocess.TimeoutExpired:
        result.error = f"Timeout after {OPENCLAW_TIMEOUT}s"
    except Exception as e:
        result.error = str(e)

    return result


def run(cases: list[dict], max_cases: int | None = None) -> list[CaseScore]:
    """
    Run Tier 2 benchmark sequentially (each turn invokes openclaw CLI).
    Set max_cases to limit run time during development.
    """
    selected = cases[:max_cases] if max_cases else cases
    scores: list[CaseScore] = []

    for i, case in enumerate(selected):
        print(f"  [{i+1}/{len(selected)}] {case['test_id']} ... ", end="", flush=True)
        result = run_case(case)
        score = score_case(result)
        scores.append(score)
        if result.error:
            print(f"ERROR: {result.error}")
        else:
            print(f"ON={score.response_recall_on:.0%} OFF={score.response_recall_off:.0%} "
                  f"Δ={score.delta_t2:+.0%}")

    return scores
