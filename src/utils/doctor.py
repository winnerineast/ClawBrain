# Generated from design/utils_onboarding.md v1.1
import os
import httpx
import asyncio
from pathlib import Path
from src.memory.storage import Hippocampus, clear_chroma_clients

def side_by_side_report(items: list):
    print(f"\n{'CHECK':<33} | {'STATUS'}")
    print("-" * 70)
    for check, status in items:
        print(f"{check:<33} | {status}")
    print("-" * 70)

async def check_health():
    print("🩺 ClawBrain System Doctor")
    print("=" * 70)
    
    report = []
    
    # 1. Environment & DB
    db_dir = os.getenv("CLAWBRAIN_DB_DIR", "data")
    db_path = Path(db_dir)
    if db_path.exists() and os.access(db_path, os.W_OK):
        report.append(("Database Directory", f"OK ({db_dir})"))
    else:
        report.append(("Database Directory", f"FAIL (Check permissions for {db_dir})"))

    # 2. ChromaDB Connection
    try:
        clear_chroma_clients()
        hp = Hippocampus(db_dir=db_dir)
        count = len(hp.traces_col.get()["ids"])
        report.append(("ChromaDB Connectivity", f"OK ({count} traces)"))
    except Exception as e:
        report.append(("ChromaDB Connectivity", f"FAIL ({str(e)[:30]})"))

    # 3. LLM Services (Relay Plane)
    ollama_url = "http://localhost:11434/api/tags"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(ollama_url)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                report.append(("Ollama Service", f"OK ({len(models)} models)"))
            else:
                report.append(("Ollama Service", f"WARN (HTTP {resp.status_code})"))
    except:
        report.append(("Ollama Service", "OFFLINE"))

    # 4. Distillation Backend (Cognitive Plane)
    distill_url = os.getenv("CLAWBRAIN_DISTILL_URL")
    if distill_url:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(distill_url if "api" in distill_url else f"{distill_url}/v1/models")
                report.append(("Distillation Backend", f"OK ({os.getenv('CLAWBRAIN_DISTILL_MODEL')})"))
        except:
            report.append(("Distillation Backend", "UNREACHABLE"))
    else:
        report.append(("Distillation Backend", "NOT CONFIGURED"))

    side_by_side_report(report)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(check_health())
