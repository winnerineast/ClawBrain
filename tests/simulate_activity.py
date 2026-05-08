import asyncio
import httpx
import random
import time
import os
import platform
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configuration
BASE_URL = "http://localhost:11435"
SESSION_ID = f"sim-{datetime.now().strftime('%m%d-%H%M')}"

# Priority-based Vault Path Detection
current_os = platform.system().upper()
VAULT_PATH = os.getenv(f"{current_os}_CLAWBRAIN_VAULT_PATH") or os.getenv("CLAWBRAIN_VAULT_PATH")

if not VAULT_PATH:
    VAULT_PATH = str(Path.home() / "ClawBrain" / "vault")

CHAT_TOPICS = [
    ["Hey, I am working on the Alpha project.", "What is the primary tech stack for Alpha?"],
    ["Let's talk about the database.", "We moved from PostgreSQL to MongoDB for the logging service.", "Why did we switch to MongoDB?"],
    ["The weather in Tokyo is quite nice today.", "I'm planning a trip to Japan next month.", "Do you have any restaurant recommendations in Shibuya?"],
    ["I've been learning Rust recently.", "Ownership and borrowing are tricky concepts.", "Can you explain how the borrow checker works?"],
    ["We need to deploy the new microservice by Friday.", "Is the CI/CD pipeline ready?", "Who is the lead engineer for DevOps?"]
]

VAULT_CLIPS = [
    ("# Project Alpha\nTech Stack: Python 3.12, FastAPI, and ChromaDB.", "Alpha_Project.md"),
    ("# Database Migration\nService: Logging\nOld: PostgreSQL\nNew: MongoDB\nReason: Better write performance for unstructured logs.", "Database_Migration.md"),
    ("# Japan Travel\nFavorite Shibuya spots: Harajuku Gyoza Lou, Ichiran Ramen, Genki Sushi.", "Japan_Tips.md"),
    ("# Rust Notes\nBorrow Checker ensures memory safety without a GC by enforcing exclusive mutable access.", "Rust_Ownership.md"),
    ("# Infrastructure Team\nLead Engineer: Sarah Chen\nDevOps: James Miller", "Team_Contacts.md")
]

async def simulate_chat():
    print(f"🚀 Starting Chat Simulation for Session: {SESSION_ID}")
    async with httpx.AsyncClient(timeout=15.0) as client:
        topic = random.choice(CHAT_TOPICS)
        for msg in topic:
            print(f"💬 [Relay Plane] Sending Chat: {msg}")
            payload = {
                "session_id": SESSION_ID,
                "content": msg
            }
            try:
                # 1. Ingest
                resp = await client.post(f"{BASE_URL}/v1/ingest", json=payload)
                print(f" ✅ Ingested (Trace: {resp.json().get('trace_id')})")
                
                await asyncio.sleep(2)
                
                # 2. Trigger Universal Completion (triggers retrieval)
                print(f" 🔍 [Relay Plane] Requesting Context for: {msg[:25]}...")
                q_payload = {
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": msg}],
                    "session_id": SESSION_ID,
                    "stream": False
                }
                await client.post(f"{BASE_URL}/v1/universal/chat/completions", json=q_payload)
            except Exception as e:
                print(f" ❌ Chat error: {e}")
            
            await asyncio.sleep(4)

def simulate_vault():
    print(f"🚀 Starting Vault Simulation at: {VAULT_PATH}")
    path = Path(VAULT_PATH)
    try:
        path.mkdir(parents=True, exist_ok=True)
        
        content, filename = random.choice(VAULT_CLIPS)
        file_path = path / filename
        
        print(f"📝 [Cognitive Plane] Writing Vault Clip: {filename}")
        file_path.write_text(content)
        
        # Update mtime to ensure scanner sees it
        os.utime(file_path, None)
        print(f" ✅ Clip saved. Scanner will pick it up on next cycle.")
    except Exception as e:
        print(f" ❌ Vault error: {e}")

async def main():
    print("=== ClawBrain Information Flow Simulator ===")
    print(f"Target: {BASE_URL}")
    print(f"Vault:  {VAULT_PATH}")
    
    count = 0
    while True:
        count += 1
        print(f"\n--- Cycle {count} ---")
        
        # High probability of chat activity
        if random.random() > 0.3:
            await simulate_chat()
        
        # Lower probability of vault activity
        if random.random() > 0.5:
            simulate_vault()
            
        print("\nSleeping for 15s...")
        await asyncio.sleep(15)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
    except Exception as e:
        print(f"Fatal error: {e}")
