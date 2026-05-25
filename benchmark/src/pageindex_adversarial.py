# Generated for Deep Reasoning Benchmark (Issue #48 / v1.3)
import asyncio
import json
import os
import time
import hashlib
from pathlib import Path
from src.memory.router import MemoryRouter

# Adversarial Data: Complex DJI Mavic Pro Technical Manual Simulation
MAVIC_MANUAL = """
# DJI Mavic Pro Technical Specifications v1.1

## Section 1: Standard Flight Operations
In normal conditions, the Mavic Pro operates at a standard efficiency level.
The default system voltage for standard battery output is **11.4V**.
This section is for reference during training flights and standard commercial photography.
""" + "NOISE LINE TO FILL SPACE AND DISTRACT VECTOR SEARCH.\n" * 150 + """

## Section 2: Extreme Environment Mode
When operating in high altitude (>3000m) or sub-zero temperatures, the drone enters Extreme Environment Mode.
In this mode, to maintain motor stability and prevent signal loss, the system voltage is boosted to **13.2V**.
Warning: Battery life will be reduced by 25% in this mode.
""" + "MORE NOISE TO SEPARATE CHUNKS AND FORCE RETRIEVAL FAILURE IN TRADITIONAL RAG.\n" * 150 + """

## Section 3: Storage and Maintenance
Store batteries at 50% charge. Never expose to temperatures above 60C. 
Calibration of the compass is required every 10 flight hours.
"""

async def run_benchmark():
    """
    [NO-MOCK] Real adversarial benchmark comparing Vector vs PageIndex using local LLM.
    """
    print("\n" + "="*70)
    print("🦞 CLAWBRAIN ADVERSARIAL BENCHMARK: VECTOR VS PAGEINDEX")
    print("="*70)
    
    db_dir = Path("benchmark/data/tmp_adversarial")
    vault_dir = Path("benchmark/data/vault_adversarial")
    if db_dir.exists(): import shutil; shutil.rmtree(db_dir)
    if vault_dir.exists(): import shutil; shutil.rmtree(vault_dir)
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "Mavic_Manual.md").write_text(MAVIC_MANUAL)
    
    os.environ["CLAWBRAIN_VAULT_PATH"] = str(vault_dir)
    os.environ["CLAWBRAIN_DISABLE_COGNITIVE_JUDGE"] = "true"
    
    # 1. Initialize Memory Router (Will auto-discover LM Studio)
    router = MemoryRouter(db_dir=str(db_dir))
    await router.wait_until_ready()
    
    # 2. Build Memory Trees (Cognitive Plane)
    print("\n🛠 [Cognitive Plane] Indexing and Building Reasoning Tree...")
    start_index = time.time()
    await router.vault_indexer.scan()
    # Build tree using real LLM
    await router.page_indexer.build_tree(vault_dir / "Mavic_Manual.md")
    print(f"✅ Indexing complete in {time.time() - start_index:.1f}s")
    
    # 3. The Adversarial Query
    # This query intentionally targets the fact in Section 2, which is surrounded by noise.
    query = "What is the boost voltage required for motor stability in Extreme Environment Mode?"
    print(f"\n🔍 Query: {query}")
    
    # Path A: Traditional Vector Retrieval (Hippocampus/Vault Search)
    print("\n--- Path A: Traditional Vector Search (Top Candidate) ---")
    start_vec = time.time()
    res_vec = router.vault_indexer.search(query, limit=1)
    vec_content = res_vec[0]["content"] if res_vec else "No Match"
    print(f"Latency: {time.time() - start_vec:.3f}s")
    print(f"Snippet: {vec_content[:150]}...")
    
    # Check if Vector found the correct fact (13.2V) or the decoy fact (11.4V)
    vector_correct = "13.2V" in vec_content and "11.4V" not in vec_content
    print(f"Outcome: {'SUCCESS' if vector_correct else 'FAIL (Vibe-based error)'}")
    
    # Path B: PageIndex Reasoning (Hybrid Path)
    print("\n--- Path B: PageIndex Reasoning (Deep Mining) ---")
    start_pi = time.time()
    context = await router.get_combined_context("bench_session", query)
    print(f"Latency: {time.time() - start_pi:.1f}s")
    
    # Check for presence of EXACT SOURCE and the correct voltage
    pageindex_correct = "13.2V" in context and "EXACT SOURCE" in context
    print(f"Outcome: {'SUCCESS' if pageindex_correct else 'FAIL'}")

    print("\n" + "="*70)
    print("FINAL BENCHMARK SCORE")
    print("-" * 70)
    print(f"Traditional Vector RAG:   {'✅ PASS' if vector_correct else '❌ FAIL'}")
    print(f"Enhanced PageIndex RAG:   {'✅ PASS' if pageindex_correct else '❌ FAIL'}")
    print("="*70 + "\n")
    
    await router.aclose()
    # Cleanup
    import shutil
    shutil.rmtree(db_dir); shutil.rmtree(vault_dir)

if __name__ == "__main__":
    try:
        asyncio.run(run_benchmark())
    except Exception as e:
        print(f"Fatal error during benchmark: {e}")
