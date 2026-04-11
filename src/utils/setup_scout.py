# Generated from design/utils_onboarding.md v1.0
import os
import asyncio
import httpx
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("SCOUT")

class SetupScout:
    """
    Environmental Probing Utility for ClawBrain.
    Identifies local LLM services and Obsidian vaults.
    """
    
    DEFAULT_OLLAMA_URL = "http://localhost:11434"
    DEFAULT_LMSTUDIO_URL = "http://localhost:1234"

    def __init__(self):
        self.findings = {
            "distill_url": None,
            "distill_model": None,
            "distill_provider": None,
            "vault_path": None,
            "db_dir": str(Path.cwd() / "data")
        }

    async def probe_ollama(self) -> bool:
        """Check for local Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.DEFAULT_OLLAMA_URL}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    if models:
                        self.findings["distill_url"] = self.DEFAULT_OLLAMA_URL
                        self.findings["distill_provider"] = "ollama"
                        self.findings["distill_model"] = models[0]["name"]
                        logger.info(f"🔎 Found Ollama with model: {self.findings['distill_model']}")
                        return True
        except:
            pass
        return False

    async def probe_lmstudio(self) -> bool:
        """Check for local LM Studio instance."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.DEFAULT_LMSTUDIO_URL}/v1/models")
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        # Only set if Ollama wasn't found (prefer Ollama for distillation)
                        if not self.findings["distill_url"]:
                            self.findings["distill_url"] = self.DEFAULT_LMSTUDIO_URL
                            self.findings["distill_provider"] = "openai"
                            self.findings["distill_model"] = models[0]["id"]
                        logger.info(f"🔎 Found LM Studio with model: {models[0]['id']}")
                        return True
        except:
            pass
        return False

    def probe_vault(self):
        """Search for common Obsidian Vault locations or create a default one."""
        search_paths = [
            Path.home() / "Documents",
            Path.home() / "Obsidian",
            Path.home()
        ]
        
        found_path = None
        for base in search_paths:
            if not base.exists():
                continue
            # Look for .obsidian config folders
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
            # P35: No vault found, create a default ClawBrain Vault
            default_vault = Path.home() / "ClawBrain" / "vault"
            default_vault.mkdir(parents=True, exist_ok=True)
            (default_vault / ".obsidian").mkdir(exist_ok=True)
            
            welcome_file = default_vault / "Welcome to ClawBrain.md"
            if not welcome_file.exists():
                welcome_file.write_text("# Welcome to ClawBrain\n\nThis is your local Knowledge Vault. You can open this folder in Obsidian to manage your agent's long-term knowledge.")
            
            self.findings["vault_path"] = str(default_vault)
            logger.info(f"✨ Created default ClawBrain Vault at: {default_vault}")

    def generate_env(self):
        """Create or update .env file based on findings, preserving existing values."""
        env_path = Path.cwd() / ".env"
        existing = {}
        
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

        # Mapping findings to ENV keys
        mapping = {
            "CLAWBRAIN_DB_DIR": self.findings["db_dir"],
            "CLAWBRAIN_DISTILL_URL": self.findings["distill_url"],
            "CLAWBRAIN_DISTILL_MODEL": self.findings["distill_model"],
            "CLAWBRAIN_DISTILL_PROVIDER": self.findings["distill_provider"],
            "CLAWBRAIN_VAULT_PATH": self.findings["vault_path"]
        }

        # Update existing with findings if keys are missing
        for key, value in mapping.items():
            if key not in existing and value:
                existing[key] = value

        # Ensure default context chars
        if "CLAWBRAIN_MAX_CONTEXT_CHARS" not in existing:
            existing["CLAWBRAIN_MAX_CONTEXT_CHARS"] = "2000"

        # Final write
        lines = [f"{k}={v}" for k, v in existing.items()]
        env_path.write_text("\n".join(lines) + "\n")
        logger.info(f"✨ Updated .env with optimal settings.")

async def main():
    scout = SetupScout()
    logger.info("🚀 Starting environment discovery...")
    
    await asyncio.gather(
        scout.probe_ollama(),
        scout.probe_lmstudio()
    )
    
    scout.probe_vault()
    scout.generate_env()
    
    logger.info("\n✅ Setup complete. You can now start the server.")

if __name__ == "__main__":
    asyncio.run(main())
