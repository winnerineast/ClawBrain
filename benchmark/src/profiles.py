#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
OpenClaw profile setup for the benchmark (V8 - Qwen 3.6 35b).
Uses the actual OpenClaw binary to generate valid schemas.
"""
import json
import os
import subprocess
import shutil
import sys
from pathlib import Path

PLUGIN_DIST = Path(__file__).parent.parent.parent / "packages" / "openclaw-pkg" / "dist"
HOME = Path.home()

# Profile names used by the runner
ID_ON  = "bm_on"
ID_OFF = "bm_off"

# Physical directories managed by OpenClaw
PROFILE_ON_DIR  = HOME / f".openclaw-{ID_ON}"
PROFILE_OFF_DIR = HOME / f".openclaw-{ID_OFF}"

# P45: Updated model to Qwen 3.6 (35b) for superior logic
TARGET_MODEL = "ollama/qwen3.6:35b-a3b"


def _setup_single_profile(profile_id: str, profile_dir: Path, is_on: bool) -> None:
    print(f"  Setting up profile: {profile_id}...")
    
    # 1. Start fresh
    if profile_dir.exists():
        try:
            shutil.rmtree(profile_dir)
        except Exception: pass
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Use OFFICIAL CLI to generate a valid config structure
    try:
        subprocess.run([
            "openclaw", "--profile", profile_id, 
            "agents", "add", "bm_agent",
            "--model", TARGET_MODEL,
            "--non-interactive",
            "--workspace", str(profile_dir / "workspace")
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"    ERROR: CLI failed to initialize profile {profile_id}: {e.stderr.decode()}")
        return

    # 3. Surgically inject the plugin configuration
    config_path = profile_dir / "openclaw.json"
    plugin_abs_path = str(PLUGIN_DIST.parent.resolve())
    
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
        
        # P44: Manual Plugin Registration (Bypass CLI install)
        config["plugins"] = {
            "slots": {
                "contextEngine": "clawbrain" if is_on else "legacy"
            },
            "entries": {
                "clawbrain": {"enabled": is_on},
                "ollama": {"enabled": True}
            },
            "installs": {
                "clawbrain": {
                    "source": "path",
                    "sourcePath": plugin_abs_path,
                    "installPath": str(HOME / ".openclaw" / "extensions" / "clawbrain"),
                    "version": "1.0.0"
                }
            },
            "allow": ["clawbrain", "ollama"]
        }
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    # 4. Sync Auth Store
    source_auth = HOME / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
    dest_auth_dir = profile_dir / "agents" / "bm_agent" / "agent"
    if source_auth.exists():
        dest_auth_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_auth, dest_auth_dir / "auth-profiles.json")
        print(f"    Synced auth store.")


def setup_profiles(force: bool = False) -> None:
    print(f"\nInitializing OpenClaw benchmark profiles with {TARGET_MODEL}...")
    _setup_single_profile(ID_ON,  PROFILE_ON_DIR,  True)
    _setup_single_profile(ID_OFF, PROFILE_OFF_DIR, False)
    print("\nProfiles ready for Qwen-based Tier 2 evaluation.")


def verify_profiles() -> tuple[bool, str]:
    return (PROFILE_ON_DIR.exists() and PROFILE_OFF_DIR.exists()), ""
