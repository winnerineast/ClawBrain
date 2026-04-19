#!/usr/bin/env python3
# Generated from design/benchmark.md v1.1
"""
Tier 2 runner: drives the full OpenClaw CLI pipeline (V18 - Toggle Mode).
Physically installs/uninstalls the plugin to ensure absolute purity.
"""
import subprocess
import time
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from evaluate import CaseScore, score_case
from profiles import install_plugin, uninstall_plugin

OPENCLAW_BIN = "openclaw"

def _run_turn(
    session_id: str,
    message: str,
    turn_num: int = 0
) -> tuple[str, float]:
    """Send one message via openclaw agent using MAIN profile."""
    # Use 'bm_agent' (Ollama) which we assume is configured in main profile
    # If not, the first run will fail and user should run 'openclaw agents add bm_agent'
    cmd = [
        OPENCLAW_BIN,
        "agent",
        "--local",
        "--json",
        "--agent", "bm_agent",
        "--session-id", session_id,
        "--message", message,
    ]
    
    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    latency = (time.monotonic() - t0) * 1000

    if proc.returncode != 0:
        error_msg = proc.stderr.strip() or f"Exit {proc.returncode}"
        raise Exception(f"openclaw exited {proc.returncode}: {error_msg}")

    try:
        # P47: Robust JSON extraction
        raw_out = proc.stdout.strip()
        start = raw_out.find('{')
        end = raw_out.rfind('}')
        if start != -1 and end != -1:
            json_str = raw_out[start:end+1]
            data = json.loads(json_str)
        else:
            raise ValueError("No JSON object found in stdout")

        if "payloads" in data and len(data["payloads"]) > 0:
            text = data["payloads"][0].get("text", "")
        else:
            text = data.get("finalAssistantVisibleText", "")
        return text, latency
    except Exception as e:
        raise Exception(f"Failed to parse JSON: {e}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")


def _run_conversation(session_id: str, turns: list[dict]) -> tuple[str, float]:
    last_response = ""
    total_latency = 0.0
    user_turns = [t for t in turns if t["role"] == "user"]
    for i, turn in enumerate(user_turns):
        resp, lat = _run_turn(session_id, turn["content"], turn_num=i+1)
        last_response = resp
        total_latency += lat
    return last_response, total_latency


def run_segment(cases: list[dict], is_on: bool) -> dict[str, str]:
    """Run a list of cases and return a map of {test_id: response}."""
    results = {}
    mode_str = "ON" if is_on else "OFF"
    
    if is_on: install_plugin()
    else: uninstall_plugin()
    
    print(f"\n--- Starting Tier 2 {mode_str} Segment ---")
    for i, case in enumerate(cases):
        tid = case["test_id"]
        sid = f"bm-{tid}-{mode_str.lower()}"
        print(f"  [{i+1}/{len(cases)}] {tid} ({mode_str})... ", end="", flush=True)
        try:
            # 1. Setup
            if "conversation_setup" in case:
                _run_conversation(sid + "-setup", case["conversation_setup"])
            # 2. Recall
            resp, _ = _run_conversation(sid, case["conversation"])
            results[tid] = resp
            print("Done")
        except Exception as e:
            print(f"ERROR: {e}")
            results[tid] = f"ERROR: {e}"
            
    return results
