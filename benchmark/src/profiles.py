#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
OpenClaw profile setup for the benchmark.

benchmark-on:  contextEngine = "clawbrain" (ClawBrain plugin enabled)
benchmark-off: contextEngine = "legacy"   (OpenClaw built-in, no ClawBrain)

Profiles live at ~/.openclaw-benchmark-{on,off}/openclaw.json
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_DIST = Path(__file__).parent.parent.parent / "packages" / "openclaw" / "clawbrain"
HOME = Path.home()
MAIN_CONFIG = HOME / ".openclaw" / "openclaw.json"

PROFILE_ON  = HOME / ".openclaw-benchmark-on"
PROFILE_OFF = HOME / ".openclaw-benchmark-off"


def _load_main_config() -> dict:
    """Load ~/.openclaw/openclaw.json as the base for both profiles."""
    with open(MAIN_CONFIG) as f:
        return json.load(f)


def _make_config_on(base: dict) -> dict:
    """Merge ClawBrain plugin settings into a copy of the main config."""
    import copy
    cfg = copy.deepcopy(base)
    plugins = cfg.setdefault("plugins", {})
    plugins.setdefault("slots", {})["contextEngine"] = "clawbrain"
    plugins.setdefault("entries", {})["clawbrain"] = {"enabled": True}
    plugins.setdefault("load", {}).setdefault("paths", [])
    if str(PLUGIN_DIST) not in plugins["load"]["paths"]:
        plugins["load"]["paths"].append(str(PLUGIN_DIST))
    return cfg


def _make_config_off(base: dict) -> dict:
    """Use main config unchanged — default contextEngine is 'legacy'."""
    import copy
    cfg = copy.deepcopy(base)
    # Explicitly set legacy to be unambiguous
    cfg.setdefault("plugins", {}).setdefault("slots", {})["contextEngine"] = "legacy"
    return cfg


def _write_config(profile_dir: Path, config: dict) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    config_path = profile_dir / "openclaw.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Written: {config_path}")


def setup_profiles(force: bool = False) -> None:
    if not MAIN_CONFIG.exists():
        print(f"ERROR: Main config not found at {MAIN_CONFIG}")
        sys.exit(1)

    # Build plugin dist if missing
    if not PLUGIN_DIST.exists():
        print(f"Plugin dist not found at {PLUGIN_DIST}. Building...")
        pkg_dir = PLUGIN_DIST.parent.parent
        subprocess.run(["npm", "run", "build"], cwd=str(pkg_dir), check=True)
        print("  Plugin built.")

    base = _load_main_config()

    print("\nSetting up OpenClaw benchmark profiles (based on ~/.openclaw/openclaw.json)...")
    _write_config(PROFILE_ON,  _make_config_on(base))
    _write_config(PROFILE_OFF, _make_config_off(base))

    print("\nProfiles:")
    print(f"  benchmark-on  → {PROFILE_ON}")
    print(f"  benchmark-off → {PROFILE_OFF}")
    print("\nTest with:")
    print("  openclaw --profile benchmark-on  agent --local --json --session-id test "
          "--message 'hello'")
    print("  openclaw --profile benchmark-off agent --local --json --session-id test "
          "--message 'hello'")


def verify_profiles() -> tuple[bool, str]:
    """Returns (ok, error_message)."""
    if not PROFILE_ON.exists():
        return False, f"Profile directory missing: {PROFILE_ON}. Run: python run_benchmark.py setup-profiles"
    if not PROFILE_OFF.exists():
        return False, f"Profile directory missing: {PROFILE_OFF}. Run: python run_benchmark.py setup-profiles"
    if not PLUGIN_DIST.exists():
        return False, f"Plugin dist missing: {PLUGIN_DIST}. Run: cd packages/openclaw && npm run build"
    return True, ""
