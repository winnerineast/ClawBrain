# Generated from design/utils_onboarding.md v1.4
import os
import asyncio
import httpx
import logging
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.utils.llm_client import HardwareProfiler

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("SCOUT")

class LLMService:
    """Metadata and orchestration logic for an LLM provider."""
    def __init__(self, name: str, port: int, macos_app: str = None, linux_bin: str = None, health_path: str = "/"):
        self.name = name
        self.port = port
        self.url = f"http://localhost:{port}"
        self.macos_app = macos_app
        self.linux_bin = linux_bin
        self.health_path = health_path

    async def is_running(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                resp = await client.get(f"{self.url}{self.health_path}")
                return resp.status_code == 200
        except:
            return False

    def start(self):
        system = platform.system()
        logger.info(f"🚀 Attempting to auto-activate {self.name}...")
        
        if system == "Darwin" and self.macos_app:
            app_path = f"/Applications/{self.macos_app}.app"
            if os.path.exists(app_path):
                subprocess.Popen(["open", "-a", self.macos_app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        elif system == "Linux" and self.linux_bin:
            bin_path = shutil.which(self.linux_bin)
            if bin_path:
                if self.name == "Ollama":
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen([bin_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        return False

class SetupScout:
    """
    Environmental Probing and Orchestration Utility for ClawBrain.
    Identifies hardware resources and local LLM services.
    """
    
    def __init__(self):
        self.services = [
            LLMService("Ollama", 11434, macos_app="Ollama", linux_bin="ollama", health_path="/api/tags"),
            LLMService("LM Studio", 1234, macos_app="LM Studio", health_path="/v1/models"),
            LLMService("OMLX", 8080, macos_app="OMLX", health_path="/v1/models"),
            LLMService("vLLM", 8000, linux_bin="vllm", health_path="/v1/models"),
            LLMService("sglang", 30000, linux_bin="sglang", health_path="/v1/models"),
        ]
        self.findings = {
            "distill_url": None,
            "distill_model": None,
            "distill_provider": None,
            "vault_path": None,
            "db_dir": str(Path.cwd() / "data")
        }

    def is_path_valid_for_os(self, path_str: str) -> bool:
        if not path_str: return False
        current_os = platform.system()
        path = Path(path_str)
        if current_os == "Darwin" and path_str.startswith("/home"): return False
        if current_os == "Linux" and path_str.startswith("/Users"): return False
        try: return path.exists() or path.parent.exists()
        except: return False

    async def orchestrate_services(self):
        """Standardized discovery and activation loop."""
        for svc in self.services:
            running = await svc.is_running()
            if not running:
                if svc.start():
                    logger.info(f"⏳ Waiting for {svc.name} to initialize...")
                    for _ in range(10):
                        await asyncio.sleep(2)
                        if await svc.is_running():
                            running = True
                            logger.info(f"✅ {svc.name} is now ONLINE.")
                            break
            
            if running:
                await self.probe_service_details(svc)

    async def probe_service_details(self, svc: LLMService):
        """Fetch models and update findings based on platform preference."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{svc.url}{svc.health_path}")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", [])] if svc.name == "Ollama" else [m["id"] for m in data.get("data", [])]
                    if models:
                        best = HardwareProfiler.pick_best_model(models)
                        system = platform.system()
                        should_update = False
                        if not self.findings["distill_url"]: should_update = True
                        elif system == "Darwin" and svc.name in ["OMLX", "LM Studio"]: should_update = True
                        elif system == "Linux" and svc.name in ["vLLM", "sglang"]: should_update = True

                        if should_update:
                            self.findings["distill_url"] = svc.url
                            self.findings["distill_provider"] = "ollama" if svc.name == "Ollama" else "openai"
                            self.findings["distill_model"] = best
                        logger.info(f"🔎 Found {svc.name} with model: {best}")
        except: pass

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
                    existing[k.strip().strip('"')] = v.strip().strip('"')
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
        logger.info(f"✨ Updated .env with optimal settings.")

async def main():
    scout = SetupScout()
    logger.info("🚀 Starting environment discovery & orchestration...")
    vram = HardwareProfiler.get_vram_gb()
    tier = HardwareProfiler.get_tier()
    logger.info(f"📊 Hardware Profile: Tier {tier} ({vram:.1f}GB effectively available)")
    await scout.orchestrate_services()
    scout.probe_vault()
    scout.generate_env()
    logger.info("\n✅ Setup complete. You can now start the server.")

if __name__ == "__main__":
    asyncio.run(main())
