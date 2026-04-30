# Generated from design/utils_onboarding.md v1.3
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
    v1.3: Platform fingerprinting and reachability validation.
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
            "db_dir": str(Path.cwd() / "data"),
            "platform": platform.system()
        }

    def is_path_valid_for_os(self, path_str: str) -> bool:
        """Verify if a path is valid and reachable for the current operating system."""
        if not path_str: return False
        current_os = platform.system()
        clean_path = path_str.strip('"').strip("'")
        if current_os == "Darwin" and clean_path.startswith("/home"): return False
        if current_os == "Linux" and clean_path.startswith("/Users"): return False
        try: 
            path = Path(clean_path)
            return path.exists() or path.parent.exists()
        except: return False

    async def is_url_reachable(self, url: str) -> bool:
        """Ping the URL to see if the service is actually alive."""
        if not url: return False
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                # Support both /v1/models and /api/tags (Ollama)
                probe_url = f"{url.rstrip('/')}/api/tags" if "11434" in url else f"{url.rstrip('/')}/v1/models"
                resp = await client.get(probe_url)
                return resp.status_code in [200, 404, 401] # 404/401 means server is there but path is different
        except:
            return False

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

    async def generate_env(self):
        env_path = Path.cwd() / ".env"
        existing = {}
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip().strip('"').strip("'")
        
        current_platform = platform.system()
        stored_platform = existing.get("CLAWBRAIN_PLATFORM", "unknown")
        
        force_reprobe = current_platform != stored_platform
        if force_reprobe:
            logger.info(f"🚀 Platform Shift Detected ({stored_platform} -> {current_platform}). Invalidating cross-platform settings.")
        
        # 1. Validate Distill URL reachability
        if "CLAWBRAIN_DISTILL_URL" in existing and not force_reprobe:
            if not await self.is_url_reachable(existing["CLAWBRAIN_DISTILL_URL"]):
                logger.info(f"⚠️ Distillation endpoint {existing['CLAWBRAIN_DISTILL_URL']} is unreachable. Re-probing...")
                force_reprobe = True

        current_platform = platform.system().upper()
        platform_prefix = f"{current_platform}_"
        
        mapping = {
            "CLAWBRAIN_DB_DIR": self.findings["db_dir"],
            "CLAWBRAIN_DISTILL_URL": self.findings["distill_url"],
            "CLAWBRAIN_DISTILL_MODEL": self.findings["distill_model"],
            "CLAWBRAIN_DISTILL_PROVIDER": self.findings["distill_provider"],
            "CLAWBRAIN_VAULT_PATH": self.findings["vault_path"],
            "CLAWBRAIN_PLATFORM": platform.system()
        }
        
        for key, value in mapping.items():
            if key == "CLAWBRAIN_PLATFORM":
                existing[key] = value
                continue
                
            p_key = f"{platform_prefix}{key}"
            
            # 1. Update platform-specific key
            if p_key not in existing or force_reprobe:
                if value: existing[p_key] = value
            elif "PATH" in p_key or "DIR" in p_key:
                if not self.is_path_valid_for_os(existing[p_key]):
                    logger.info(f"🔄 Correcting invalid platform path: {p_key}")
                    existing[p_key] = value
            
            # 2. Synchronize generic key for the current platform
            if value: existing[key] = value
        
        if "CLAWBRAIN_MAX_CONTEXT_CHARS" not in existing:
            existing["CLAWBRAIN_MAX_CONTEXT_CHARS"] = "2000"
            
        # Re-sort to keep it clean (platform specific together)
        sorted_keys = sorted(existing.keys())
        lines = [f'{k}="{existing[k]}"' for k in sorted_keys]
        env_path.write_text("\n".join(lines) + "\n")
        logger.info(f"✨ Updated .env with platform-optimized settings ({current_platform} specific).")

async def main():
    scout = SetupScout()
    logger.info("🚀 Starting environment discovery...")
    vram = HardwareProfiler.get_vram_gb()
    tier = HardwareProfiler.get_tier()
    logger.info(f"📊 Hardware Profile: Tier {tier} ({vram:.1f}GB effectively available)")
    await asyncio.gather(scout.probe_ollama(), scout.probe_lmstudio(), scout.probe_omlx())
    scout.probe_vault()
    await scout.generate_env()
    logger.info("\n✅ Setup complete. You can now start the server.")

if __name__ == "__main__":
    asyncio.run(main())
