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
OPENCLAW_TIMEOUT = int(os.getenv("OPENCLAW_TURN_TIMEOUT", "1200"))  # 10x timeout: 1200 seconds


def _run_turn(
    profile: str,
    session_id: str,
    message: str,
    turn_num: int = 0
) -> tuple[str, float]:
    """
    Send one message via openclaw agent --local --json.
    Returns (response_text, latency_ms).
    Raises on non-zero exit or JSON parse failure.
    """
    print(f"    [Turn {turn_num}] Sending message... ", end="", flush=True)
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
    print(f"Done ({latency_ms/1000:.1f}s)")

    # openclaw writes JSON output to stderr; stdout is always empty
    output = proc.stderr

    if proc.returncode != 0:
        raise RuntimeError(
            f"openclaw exited {proc.returncode}: {output[:500]}"
        )

    # Strip ANSI colour codes before parsing JSON
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    clean = ansi_escape.sub('', output)
    
    # openclaw might output multiple JSON objects or logs before the final response.
    # We look for the LAST JSON object in the output which contains "payloads".
    matches = list(re.finditer(r'\{.*\}', clean, re.DOTALL))
    if not matches:
        raise ValueError(f"No JSON found in stderr: {clean[:300]}")
    
    # Try parsing from the last match and work backwards if needed
    data = None
    for m in reversed(matches):
        try:
            potential_json = m.group(0)
            data = json.loads(potential_json)
            if "payloads" in data:
                break
            data = None
        except json.JSONDecodeError:
            continue
            
    if data is None:
        raise ValueError(f"No valid response JSON with 'payloads' found in stderr")

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

    user_turns = [t for t in conversation if t["role"] == "user"]
    for i, turn in enumerate(user_turns):
        text, lat = _run_turn(profile, session_id, turn["content"], turn_num=i+1)
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
        # ── ClawBrain ON ───────────────────────────────────────────────────
        # Setup session (if isolation test)
        if "session_id_setup" in case and "conversation_setup" in case:
            setup_session_on = case["session_id_setup"] + "-t2-on"
            setup_user_turns = [t for t in case["conversation_setup"] if t["role"] == "user"]
            print(f"\n    [Setup ON] session={setup_session_on}")
            for i, turn in enumerate(setup_user_turns):
                _run_turn("benchmark-on", setup_session_on, turn["content"], turn_num=i+1)

        print(f"\n    [Run ON] profile=benchmark-on session={session_on}")
        resp_on, lat_on = _run_conversation(
            "benchmark-on", session_on, case["conversation"]
        )
        result.response_on = resp_on
        result.latency_ms_t2 = lat_on

        # ── ClawBrain OFF (legacy engine) ─────────────────────────────────
        print(f"\n    [Run OFF] profile=benchmark-off session={session_off}")
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
