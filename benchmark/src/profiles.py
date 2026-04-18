#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
OpenClaw profile setup for the benchmark (V18 - Toggle Strategy).
Manages the plugin in the MAIN profile.
"""
import json
import os
import subprocess
import shutil
import sys
from pathlib import Path

PLUGIN_SRC  = Path(__file__).parent.parent.parent / "packages" / "openclaw-pkg"
HOME = Path.home()
EXT_DIR = HOME / ".openclaw" / "extensions" / "clawbrain"
MAIN_CONFIG = HOME / ".openclaw" / "openclaw.json"


def install_plugin() -> None:
    """Physically install and authorize the plugin in the main profile."""
    print("  Installing ClawBrain plugin (ON mode)...")
    
    # 1. Physical copy
    EXT_DIR.parent.mkdir(parents=True, exist_ok=True)
    if EXT_DIR.exists():
        shutil.rmtree(EXT_DIR)
    shutil.copytree(PLUGIN_SRC.resolve(), EXT_DIR)
    
    # 2. Update openclaw.json
    if MAIN_CONFIG.exists():
        with open(MAIN_CONFIG, "r") as f:
            config = json.load(f)
        
        plugins = config.setdefault("plugins", {})
        
        # Add to allow list
        allowed = plugins.setdefault("allow", [])
        if "clawbrain" not in allowed: allowed.append("clawbrain")
        
        # Set contextEngine slot
        slots = plugins.setdefault("slots", {})
        slots["contextEngine"] = "clawbrain"
        
        # Ensure enabled
        entries = plugins.setdefault("entries", {})
        entries["clawbrain"] = {"enabled": True}
        
        # Add to installs metadata
        installs = plugins.setdefault("installs", {})
        installs["clawbrain"] = {
            "source": "path",
            "sourcePath": str(PLUGIN_SRC.resolve()),
            "installPath": str(EXT_DIR),
            "version": "1.0.0"
        }
        
        with open(MAIN_CONFIG, "w") as f:
            json.dump(config, f, indent=2)
    print("    Plugin installed and authorized.")


def uninstall_plugin() -> None:
    """Completely remove the plugin and revert config (OFF mode)."""
    print("  Uninstalling ClawBrain plugin (OFF mode)...")
    
    # 1. Physical removal
    if EXT_DIR.exists():
        shutil.rmtree(EXT_DIR)
    
    # 2. Update openclaw.json
    if MAIN_CONFIG.exists():
        with open(MAIN_CONFIG, "r") as f:
            config = json.load(f)
        
        plugins = config.setdefault("plugins", {})
        
        # Revert contextEngine slot
        slots = plugins.setdefault("slots", {})
        slots["contextEngine"] = "legacy"
        
        # Remove from allow list
        if "allow" in plugins and "clawbrain" in plugins["allow"]:
            plugins["allow"].remove("clawbrain")
            
        # Clean up entries and installs
        if "entries" in plugins and "clawbrain" in plugins["entries"]:
            del plugins["entries"]["clawbrain"]
        if "installs" in plugins and "clawbrain" in plugins["installs"]:
            del plugins["installs"]["clawbrain"]

        with open(MAIN_CONFIG, "w") as f:
            json.dump(config, f, indent=2)
    print("    Plugin uninstalled. Baseline restored.")


def setup_profiles(force: bool = False) -> None:
    # No-op in toggle mode, just verifies the main config exists
    if not MAIN_CONFIG.exists():
        print(f"ERROR: Main config not found at {MAIN_CONFIG}")
        sys.exit(1)
    print("Toggle-based benchmark ready. Use runner to switch modes.")


def verify_profiles() -> tuple[bool, str]:
    return MAIN_CONFIG.exists(), ""
