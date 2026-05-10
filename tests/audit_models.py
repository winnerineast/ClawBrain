# Generated from design/test_sanitization.md v1.1
import asyncio
import httpx
import platform
from typing import List, Tuple
from src.utils.llm_client import LLMFactory, HardwareProfiler

async def test_model_capability(client, name: str) -> dict:
    results = {"name": name, "summary_ok": False, "reasoning_ok": False, "error": ""}
    
    # 1. Test Summarization (Long Context)
    text = "The system voltage for high altitude missions is strictly 48V. Standard ground voltage is 12V."
    try:
        res = await client.generate(
            prompt=f"Summarize this precisely: {text}",
            system="You are a technical indexer."
        )
        if res and len(res.strip()) > 10 and "[Error]" not in res:
            results["summary_ok"] = True
    except Exception as e:
        results["error"] += f"Summary failed: {e}; "

    # 2. Test Reasoning (Instruction Following)
    choices = "[0] Alpha\n[1] Beta\n[2] Gamma"
    try:
        res = await client.generate(
            prompt=f"Which index is related to 'Beta'? Choices:\n{choices}\nRespond ONLY with the number.",
            system="You are a router."
        )
        if "1" in res:
            results["reasoning_ok"] = True
    except Exception as e:
        results["error"] += f"Reasoning failed: {e}; "
        
    return results

async def run_audit():
    print("🦞 ClawBrain LLM Capability Audit")
    print("========================================")
    
    # Discovery
    hosters = [
        ("openai", "http://localhost:8080", "/v1/models"),   # OMLX
        ("openai", "http://localhost:1234", "/v1/models"),   # LM Studio
        ("ollama", "http://localhost:11434", "/api/tags"),
    ]
    
    candidates = []
    for provider, url, path in hosters:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{url}{path}")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", [])] if provider == "ollama" else [m["id"] for m in data.get("data", [])]
                    for m in models:
                        if "embed" not in m.lower():
                            candidates.append((provider, url, m))
        except: continue

    if not candidates:
        print("❌ NO MODELS DETECTED. Please start OMLX, LM Studio, or Ollama.")
        return

    print(f"🔎 Found {len(candidates)} candidate models. Starting deep audit...\n")
    print(f"{'MODEL NAME':<50} | {'SUMMARY':<10} | {'REASONING'}")
    print("-" * 80)
    
    for provider, url, model in candidates:
        client = LLMFactory.get_client(provider, url, model)
        report = await test_model_capability(client, model)
        
        s_status = "✅ PASS" if report["summary_ok"] else "❌ FAIL"
        r_status = "✅ PASS" if report["reasoning_ok"] else "❌ FAIL"
        
        print(f"{model[:50]:<50} | {s_status:<10} | {r_status}")
        
    print("-" * 80)
    print("Audit Complete.")

if __name__ == "__main__":
    asyncio.run(run_audit())
