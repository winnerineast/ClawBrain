#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
Tier 2 runner: drives the full OpenClaw CLI pipeline.
Requires: openclaw installed, local LLM (Ollama), ClawBrain server running.

Each message is sent via:
  openclaw --profile benchmark-{on|off} agent --local --json
            --session-id <id> --message <content>

The model's response text is evaluated against ground truth.
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
    """
    print(f"    [Turn {turn_num}] Sending message... ", end="", flush=True)
    # P44: EXPLICITLY specify agent to ensure it uses Ollama (model is pre-bound to agent)
    cmd = [
        OPENCLAW_BIN,
        "--profile", profile,
        "agent",
        "--local",
        "--json",
        "--agent", "bm_agent",
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

    output = proc.stderr

    if proc.returncode != 0:
        raise RuntimeError(
            f"openclaw exited {proc.returncode}: {output[:500]}"
        )

    # Strip ANSI colour codes before parsing JSON
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    clean = ansi_escape.sub('', output)
    
    data = None
    
    def extract_json_objects(text):
        objs = []
        stack = []
        start = -1
        for i, char in enumerate(text):
            if char == '{':
                if not stack:
                    start = i
                stack.append(char)
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack:
                        objs.append(text[start:i+1])
        return objs

    potential_objs = extract_json_objects(clean)
    for obj_str in reversed(potential_objs):
        try:
            candidate = json.loads(obj_str)
            if isinstance(candidate, dict) and "payloads" in candidate:
                data = candidate
                break
        except json.JSONDecodeError:
            continue
            
    if data is None:
        raise ValueError(f"No valid response JSON found in stderr.")

    payloads = data.get("payloads", [])
    text = " ".join(p.get("text", "") for p in payloads if p.get("text"))
    return text, latency_ms


def _run_conversation(
    profile: str,
    session_id: str,
    conversation: list[dict],
) -> tuple[str, float]:
    recall_text = ""
    recall_latency = 0.0

    user_turns = [t for t in conversation if t["role"] == "user"]
    for i, turn in enumerate(user_turns):
        text, lat = _run_turn(profile, session_id, turn["content"], turn_num=i+1)
        if turn.get("is_recall_query"):
            recall_text = text
            recall_latency = lat
            break

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
        expected_output=evaluation.get("expected_output", ""),
        must_contain=evaluation.get("must_contain", []),
        must_not_contain=evaluation.get("must_not_contain", []),
        eval_type=evaluation.get("type", "exact_match"),
    )

    try:
        # ── ClawBrain ON ───────────────────────────────────────────────────
        if "session_id_setup" in case and "conversation_setup" in case:
            setup_session_on = case["session_id_setup"] + "-t2-on"
            setup_user_turns = [t for t in case["conversation_setup"] if t["role"] == "user"]
            for i, turn in enumerate(setup_user_turns):
                _run_turn("bm_on", setup_session_on, turn["content"], turn_num=i+1)

        resp_on, lat_on = _run_conversation(
            "bm_on", session_on, case["conversation"]
        )
        result.response_on = resp_on
        result.latency_ms_t2 = lat_on

        # ── ClawBrain OFF ──────────────────────────────────────────────────
        resp_off, _ = _run_conversation(
            "bm_off", session_off, case["conversation"]
        )
        result.response_off = resp_off

    except Exception as e:
        result.error = str(e)

    return result


def run(cases: list[dict], max_cases: int | None = None) -> list[CaseScore]:
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
