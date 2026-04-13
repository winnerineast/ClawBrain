
import httpx
import asyncio
import json

async def debug_one():
    url = "http://localhost:11435"
    session_id = "debug-session-999"
    
    # 1. Ingest
    print("--- Ingesting ---")
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{url}/internal/ingest", json={
            "session_id": session_id,
            "role": "user",
            "content": "The secret password is: MAGENTA-FLAMINGO-123",
            "sync": True
        })
        print(f"Ingest Resp: {resp.status_code} {resp.text}")
        
        # 2. Assemble
        print("\n--- Assembling ---")
        resp = await client.post(f"{url}/internal/assemble", json={
            "session_id": session_id,
            "current_focus": "password",
            "token_budget": 2000
        })
        print(f"Assemble Resp: {resp.status_code}")
        data = resp.json()
        addition = data.get("system_prompt_addition", "")
        print(f"Addition Length: {len(addition)}")
        print(f"Addition Preview: {addition[:200]}")
        
        if "MAGENTA-FLAMINGO-123" in addition:
            print("\nSUCCESS: Memory retrieved!")
        else:
            print("\nFAILURE: Memory not found in addition.")

if __name__ == "__main__":
    asyncio.run(debug_one())
