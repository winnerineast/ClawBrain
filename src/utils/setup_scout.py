# Generated from design/utils_onboarding.md v1.1
import os
import asyncio
import httpx
import logging
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.utils.llm_client import HardwareProfiler

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("SCOUT")

class SetupScout:
    """
    Environmental Probing Utility for ClawBrain.
    Identifies hardware resources and local LLM services.
    """
    
    DEFAULT_OLLAMA_URL = "http://localhost:11434"
    DEFAULT_LMSTUDIO_URL = "http://localhost:1234"
    DEFAULT_OMLX_URL = "http://localhost:8080"

    def __init__(self):
        self.findings = {
            "distill_url": None,
            "distill_model": None,
            "distill_provider": None,
            "vault_path": None,
            "db_dir": str(Path.cwd() / "data")
        }

    def is_path_valid_for_os(self, path_str: str) -> bool:
        """Verify if a path is valid and reachable for the current operating system."""
        if not path_str: return False
        current_os = platform.system()
        path = Path(path_str)
        if current_os == "Darwin" and path_str.startswith("/home"): return False
        if current_os == "Linux" and path_str.startswith("/Users"): return False
        try: return path.exists() or path.parent.exists()
        except: return False

    async def probe_ollama(self) -> bool:
        """Check for local Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.DEFAULT_OLLAMA_URL}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    if models:
                        best = HardwareProfiler.pick_best_model(models)
                        if not self.findings["distill_url"] or platform.system() != "Darwin":
                            self.findings["distill_url"] = self.DEFAULT_OLLAMA_URL
                            self.findings["distill_provider"] = "ollama"
                            self.findings["distill_model"] = best
                        logger.info(f"🔎 Found Ollama with model: {best}")
                        return True
        except: pass
        return False

    async def probe_lmstudio(self) -> bool:
        """Check for local LM Studio instance."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.DEFAULT_LMSTUDIO_URL}/v1/models")
                if resp.status_code == 200:
                    models = [m["id"] for m in resp.json().get("data", [])]
                    if models:
                        best = HardwareProfiler.pick_best_model(models)
                        if not self.findings["distill_url"] or platform.system() == "Darwin":
                            self.findings["distill_url"] = self.DEFAULT_LMSTUDIO_URL
                            self.findings["distill_provider"] = "openai"
                            self.findings["distill_model"] = best
                        logger.info(f"🔎 Found LM Studio with model: {best}")
                        return True
        except: pass
        return False

    async def probe_omlx(self) -> bool:
        """Check for local OMLX instance (OpenAI-compatible MLX server)."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.DEFAULT_OMLX_URL}/v1/models")
                if resp.status_code == 200:
                    models = [m["id"] for m in resp.json().get("data", [])]
                    if models:
                        best = HardwareProfiler.pick_best_model(models)
                        self.findings["distill_url"] = self.DEFAULT_OMLX_URL
                        self.findings["distill_provider"] = "openai"
                        self.findings["distill_model"] = best
                        logger.info(f"🔎 Found OMLX with model: {best}")
                        return True
        except: pass
        return False

    def probe_vault(self):
        search_paths = [Path.home() / "Documents", Path.home() / "Obsidian", Path.home()]
        found_path = None
        for base in search_paths:
            if not base.exists(): continue
            try:
                for p in base.glob("**/.obsidian"):
                    found_path = p.parent
                    break
            except: continue
            if found_path: break
        if found_path:
            self.findings["vault_path"] = str(found_path)
            logger.info(f"🔎 Found existing Obsidian Vault at: {found_path}")
        else:
            default_vault = Path.home() / "ClawBrain" / "vault"
            default_vault.mkdir(parents=True, exist_ok=True)
            (default_vault / ".obsidian").mkdir(exist_ok=True)
            welcome_file = default_vault / "Welcome to ClawBrain.md"
            if not welcome_file.exists():
                welcome_file.write_text("# Welcome to ClawBrain\n\nThis is your local Knowledge Vault.")
            self.findings["vault_path"] = str(default_vault)
            logger.info(f"✨ Created default ClawBrain Vault at: {default_vault}")

    def generate_env(self):
        env_path = Path.cwd() / ".env"
        existing = {}
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()
        mapping = {
            "CLAWBRAIN_DB_DIR": self.findings["db_dir"],
            "CLAWBRAIN_DISTILL_URL": self.findings["distill_url"],
            "CLAWBRAIN_DISTILL_MODEL": self.findings["distill_model"],
            "CLAWBRAIN_DISTILL_PROVIDER": self.findings["distill_provider"],
            "CLAWBRAIN_VAULT_PATH": self.findings["vault_path"]
        }
        for key, value in mapping.items():
            if key not in existing:
                if value: existing[key] = value
            elif "PATH" in key or "DIR" in key:
                if not self.is_path_valid_for_os(existing[key]):
                    logger.info(f"🔄 Correcting invalid path for {key}: {existing[key]} -> {value}")
                    existing[key] = value
            elif not existing[key] and value:
                existing[key] = value
        if "CLAWBRAIN_MAX_CONTEXT_CHARS" not in existing:
            existing["CLAWBRAIN_MAX_CONTEXT_CHARS"] = "2000"
        lines = [f'{k}="{v}"' for k, v in existing.items()]
        env_path.write_text("\n".join(lines) + "\n")
        logger.info(f"✨ Updated .env with optimal settings (quoted).")

async def main():
    scout = SetupScout()
    logger.info("🚀 Starting environment discovery...")
    vram = HardwareProfiler.get_vram_gb()
    tier = HardwareProfiler.get_tier()
    logger.info(f"📊 Hardware Profile: Tier {tier} ({vram:.1f}GB effectively available)")
    await asyncio.gather(scout.probe_ollama(), scout.probe_lmstudio(), scout.probe_omlx())
    scout.probe_vault()
    scout.generate_env()
    logger.info("\n✅ Setup complete. You can now start the server.")

if __name__ == "__main__":
    asyncio.run(main())
