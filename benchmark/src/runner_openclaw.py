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

from benchmark.src.evaluate import CaseScore, score_case
from benchmark.src.profiles import install_plugin, uninstall_plugin

OPENCLAW_BIN = "openclaw"

def _run_turn(
    session_id: str,
    message: str,
    turn_num: int = 0
) -> tuple[str, float]:
    """Send one message via openclaw agent using MAIN profile."""
    # Issue #41: Inject ClawBrain settings via ENV instead of invalid config keys
    env = os.environ.copy()
    env["CLAWBRAIN_URL"] = "http://127.0.0.1:11435/v1"
    env["CLAWBRAIN_TIMEOUT_MS"] = "5000"

    cmd = [
        OPENCLAW_BIN,
        "agent",
        "--local",
        "--json",
        "--thinking", "off",
        "--agent", "bm_agent",
        "--session-id", session_id,
        "--message", message,
    ]
    
    t0 = time.monotonic()
    # P47: Increased timeout for large reasoning models
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60.0)
    latency = (time.monotonic() - t0) * 1000

    if proc.returncode != 0:
        error_msg = proc.stderr.strip() or f"Exit {proc.returncode}"
        raise Exception(f"openclaw exited {proc.returncode}: {error_msg}")

    try:
        # P47/61: Robust JSON extraction
        # Some versions of OpenClaw or specific models might output the JSON to stderr
        combined_out = proc.stdout.strip() + "\n" + proc.stderr.strip()
        
        # Aggressive non-greedy search for {} blocks
        import re
        candidate_strs = re.findall(r'\{.*?\}', combined_out, re.DOTALL)
        
        data = None
        # Iterate backwards to find the actual final response object
        for s in reversed(candidate_strs):
            try:
                temp = json.loads(s)
                # Check for signature fields of an OpenClaw JSON response
                if "payloads" in temp or "finalAssistantVisibleText" in temp or "executionTrace" in temp:
                    data = temp
                    break
            except: continue
        
        if data is None:
            # Fallback: Search for the largest possible JSON block in the combined output
            # (greedy match from first { to last })
            start = combined_out.find('{')
            end = combined_out.rfind('}')
            if start != -1 and end > start:
                try: 
                    # Try to shrink the window until it parses
                    for i in range(start, end):
                        if combined_out[i] == '{':
                            try:
                                data = json.loads(combined_out[i:end+1])
                                if "payloads" in data or "finalAssistantVisibleText" in data:
                                    break
                            except: pass
                    if not data: data = json.loads(combined_out[start:end+1])
                except: pass

        if data is None:
            raise ValueError("No valid JSON response object found in output.")

        if "payloads" in data and len(data["payloads"]) > 0:
            text = data["payloads"][0].get("text", "")
        else:
            text = data.get("finalAssistantVisibleText", "")
        return text, latency
    except Exception as e:
        raise Exception(f"Failed to parse JSON: {e}\nSTDOUT: {proc.stdout[:500]}...\nSTDERR: {proc.stderr[:500]}...")


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
