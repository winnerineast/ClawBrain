# Generated from audit/diagnostic_loop.md
import pytest
import subprocess
import json
import sqlite3
import time
import os
import httpx
from pathlib import Path

# Paths
DB_PATH = "/home/nvidia/ClawBrain/data/hippocampus.db"
OPENCLAW_BIN = "openclaw" 

def visual_audit(test_name, step, expected, actual):
    print(f"\n[E2E LOOP AUDIT: {test_name}]")
    print(f"STEP: {step}")
    print("-" * 60)
    print(f"{'EXPECTED':<27} | {'ACTUAL'}")
    print(f"{str(expected)[:27]:<27} | {str(actual)[:27]}")
    print("-" * 60)

@pytest.mark.asyncio
async def test_p26_openclaw_to_clawbrain_loop():
    """
    PHASE 26: Definitive E2E Verification.
    OpenClaw CLI (benchmark-on) -> ClawBrain Relay -> Ollama -> ClawBrain Archive -> Verification.
    """
    # 0. Check if server is running
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:11435/health")
            assert resp.status_code == 200
    except Exception as e:
        pytest.fail(f"ClawBrain server not running on 11435: {e}")

    session_id = f"loop-test-{int(time.time())}"
    secret_canary = f"CANARY_SECRET_{int(time.time())}"
    
    # 1. Clean Slate
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM traces WHERE context_id = ?", (session_id,))

    # 2. Drive OpenClaw CLI
    print(f"\n[1/3] Driving OpenClaw with secret: {secret_canary}")
    
    cmd = [
        OPENCLAW_BIN,
        "--profile", "benchmark-on",
        "agent",
        "--local",
        "--session-id", session_id,
        "--message", f"Respond with exactly one word: '{secret_canary}'"
    ]
    
    try:
        # Run OpenClaw and wait for it to finish the turn
        # OpenClaw might take time to stream the full response
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if process.returncode != 0:
            print(f"STDOUT: {process.stdout}")
            print(f"STDERR: {process.stderr}")
            pytest.fail(f"OpenClaw execution failed with code {process.returncode}")
            
        print("[2/3] OpenClaw transaction complete.")
        
    except subprocess.TimeoutExpired:
        pytest.fail("OpenClaw timed out. Is Ollama responding?")

    # 3. Wait for ClawBrain async ingestion (Wait longer for SSE reconstruction)
    print("[3/3] Waiting for ClawBrain to solidify memory...")
    time.sleep(5.0)

    # 4. Database Penetration Verification
    print("\n[VERIFICATION] Searching for trace in ClawBrain Hippocampus...")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        # Find the latest trace for this session
        row = conn.execute(
            "SELECT raw_content FROM traces WHERE context_id = ? ORDER BY timestamp DESC LIMIT 1",
            (session_id,)
        ).fetchone()

    if not row:
        pytest.fail(f"FAILED: No trace recorded by ClawBrain for session {session_id}")

    data = json.loads(row["raw_content"])
    stimulus_obj = data.get("stimulus", {})
    reaction_obj = data.get("reaction", {})
    
    # Check stimulus (user message)
    stimulus_text = ""
    if "messages" in stimulus_obj:
        stimulus_text = " ".join(m.get("content", "") for m in stimulus_obj["messages"])
    
    # Check reaction (assistant response reconstructed from stream)
    reaction_text = reaction_obj.get("message", {}).get("content", "")

    visual_audit("Full Loop", "Stimulus Capture", secret_canary, stimulus_text)
    visual_audit("Full Loop", "Reaction Capture", secret_canary, reaction_text)

    # ASSERTIONS
    assert secret_canary in stimulus_text, "ClawBrain failed to record the prompt from OpenClaw."
    
    # This is the most important check: Did ClawBrain capture the SSE stream?
    assert "[Streamed]" not in reaction_text, "ClawBrain saved a placeholder instead of the real reaction."
    assert secret_canary in reaction_text, f"ClawBrain failed to capture the LLM response '{secret_canary}' from the stream."
    
    print("\n--- [E2E LOOP VERIFIED] ---")
    print("OpenClaw -> ClawBrain -> LLM -> ClawBrain Archive is FUNCTIONAL.")
