# Generated from design/test_sanitization.md v1.0
import os
import subprocess
import shutil
import httpx
import time
from pathlib import Path

def side_by_side_audit(check: str, status: str):
    print(f"{check:<33} | {status}")

def run_sanitization():
    print("🧹 ClawBrain Environment Sanitization")
    print("=" * 70)
    print(f"{'ACTION':<33} | {'RESULT'}")
    print("-" * 70)

    # 1. Process Reaper: Kill uvicorn and lms
    try:
        subprocess.run(["pkill", "-f", "uvicorn"], stderr=subprocess.DEVNULL)
        subprocess.run(["pkill", "-f", "llmster"], stderr=subprocess.DEVNULL)
        side_by_side_audit("Reaping Server Processes", "CLEARED")
    except Exception as e:
        side_by_side_audit("Reaping Server Processes", f"ERROR ({str(e)[:30]})")

    # 2. GPU & VRAM Recovery: Stop Ollama models
    try:
        result = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")[1:] # Skip header
        original_models = [line.split()[0] for line in lines if line]
        
        if original_models:
            for m in original_models:
                subprocess.run(["ollama", "stop", m])
            side_by_side_audit("GPU VRAM Recovery", f"STOPPED {len(original_models)} MODELS")
        else:
            side_by_side_audit("GPU VRAM Recovery", "IDLE (NO MODELS)")
    except Exception as e:
        side_by_side_audit("GPU VRAM Recovery", f"ERROR ({str(e)[:30]})")

    # 3. Storage & State Purge: Clear tests/data ONLY
    # CRITICAL: Do NOT touch tests/fixtures
    try:
        test_data_dir = Path("tests/data")
        if test_data_dir.exists():
            for item in test_data_dir.iterdir():
                # Double safety check: never delete 'fixtures' if it somehow ended up inside
                if item.name == "fixtures":
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            side_by_side_audit("Storage Purge (tests/data)", "EMPTIED")
        else:
            side_by_side_audit("Storage Purge (tests/data)", "SKIP (NOT FOUND)")
    except Exception as e:
        side_by_side_audit("Storage Purge (tests/data)", f"ERROR ({str(e)[:30]})")

    # 4. Pre-flight: Check Ollama
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                side_by_side_audit("Pre-flight: Ollama Service", "READY")
            else:
                side_by_side_audit("Pre-flight: Ollama Service", f"WARN (HTTP {resp.status_code})")
    except Exception as e:
        side_by_side_audit("Pre-flight: Ollama Service", "OFFLINE")

    print("-" * 70)
    print("✨ Environment is sanitized and ready for regression.\n")

if __name__ == "__main__":
    run_sanitization()
