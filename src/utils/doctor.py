# Generated from design/utils_onboarding.md v1.1
import os
import httpx
import asyncio
import logging
from pathlib import Path
from src.memory.storage import Hippocampus, clear_chroma_clients
from src.utils.llm_client import LLMFactory
from src.utils.config import get_env

logger = logging.getLogger("GATEWAY.UTILS.DOCTOR")

class SystemDoctor:
    """ClawBrain System Diagnostic Utility."""
    def __init__(self):
        self.db_dir = get_env("CLAWBRAIN_DB_DIR", "data")
        self.distill_url = get_env("CLAWBRAIN_DISTILL_URL", "http://localhost:11434")
        self.distill_provider = get_env("CLAWBRAIN_DISTILL_PROVIDER", "ollama")

    async def check_connectivity(self) -> dict:
        """Check all critical backend connections."""
        status = {"ollama": "OFFLINE", "lmstudio": "OFFLINE", "omlx": "OFFLINE"}
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            # 1. Ollama
            try:
                resp = await client.get("http://localhost:11434/api/tags")
                if resp.status_code == 200: status["ollama"] = "ONLINE"
            except: pass
            
            # 2. LM Studio
            try:
                resp = await client.get("http://localhost:1234/v1/models")
                if resp.status_code == 200: status["lmstudio"] = "ONLINE"
            except: pass
            
            # 3. OMLX
            try:
                resp = await client.get("http://localhost:8080/v1/models")
                if resp.status_code == 200: status["omlx"] = "ONLINE"
            except: pass
            
        return status

    async def verify_llm(self) -> bool:
        """Verify the configured distillation LLM is functional."""
        try:
            llm = LLMFactory.from_env()
            res = await llm.generate("Is 1+1=2? Answer only YES or NO.", system="You are a calculator.")
            return "YES" in res.upper()
        except Exception as e:
            logger.error(f"[DOCTOR] LLM verification failed: {e}")
            return False

    async def run_full_report(self):
        """Execute and print a side-by-side health report."""
        print("🩺 ClawBrain System Doctor")
        print("=" * 70)
        
        report = []
        
        # 1. Database
        db_path = Path(self.db_dir)
        if db_path.exists() and os.access(db_path, os.W_OK):
            report.append(("Database Directory", f"OK ({self.db_dir})"))
        else:
            report.append(("Database Directory", f"FAIL (Check permissions for {self.db_dir})"))

        # 2. ChromaDB
        try:
            clear_chroma_clients()
            hp = Hippocampus(db_dir=self.db_dir)
            count = len(hp.traces_col.get()["ids"])
            report.append(("ChromaDB Connectivity", f"OK ({count} traces)"))
        except Exception as e:
            report.append(("ChromaDB Connectivity", f"FAIL ({str(e)[:30]})"))

        # 3. Connectivity
        conn = await self.check_connectivity()
        report.append(("Ollama Service", conn["ollama"]))
        
        # 4. LLM
        distill_ok = await self.verify_llm()
        model = get_env('CLAWBRAIN_DISTILL_MODEL', 'UNKNOWN')
        report.append(("Distillation Backend", f"{'OK' if distill_ok else 'FAIL'} ({model})"))

        print(f"\n{'CHECK':<33} | {'STATUS'}")
        print("-" * 70)
        for check, status in report:
            print(f"{check:<33} | {status}")
        print("-" * 70)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    doc = SystemDoctor()
    asyncio.run(doc.run_full_report())
