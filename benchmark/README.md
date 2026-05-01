# ClawBrain Benchmark: Quantifying the Cognitive Delta

[中文版](./README_CN.md)

## Why Benchmark?

LLM memory is notoriously difficult to measure. Unit tests can confirm that code doesn't crash, and logs can show that data is being saved, but they cannot answer the most critical question: **Does this actually make the AI smarter?**

ClawBrain's value is defined by the **Delta**—the measurable improvement in an agent's ability to recall facts and maintain context over time compared to a standard, stateless LLM interaction. This benchmark suite provides the objective evidence required to prove that value.

## The Two-Tiered Validation Strategy

To ensure both technical precision and real-world utility, the benchmark is split into two tiers:

### Tier 1: Infrastructure Integrity (Direct API)
*   **Method**: Drives ClawBrain’s `/v1/*` endpoints directly, bypassing the LLM.
*   **Purpose**: Validates the mathematical correctness of the **Retrieval and Context Budgeting** logic.
*   **Metrics**: Verifies that the correct facts are injected into the prompt addition without exceeding token budgets. It is deterministic and fast.

### Tier 2: Cognitive Effectiveness (Real-World E2E)
*   **Method**: Drives the full stack: `OpenClaw CLI` → `ClawBrain Plugin` → `Local LLM`.
*   **Purpose**: Measures the **End-to-End utility**. It doesn't just check if a fact is in the prompt; it checks if the LLM successfully parses that memory to provide a correct answer.
*   **Metrics**: Actual recall rate in model responses and robustness against conversational noise.

## Cognitive Dimensions

We don't just test "memory"; we stress-test specific cognitive failure points that agents face in production:

| Dimension | Challenge |
|-----------|-----------|
| **Recall Distance** | Remembering a specific fact after 100+ turns of unrelated chatter. |
| **Fact Evolution** | Correcting memory when a user changes their mind (e.g., "The server moved from port 5432 to 5433"). |
| **Noise Robustness** | Extracting a "needle" fact from a "haystack" of technical jargon. |
| **Session Isolation** | Ensuring User A's private data never leaks into User B's context (100% pass required). |
| **Multi-Fact Synthesis** | Answering questions that require combining 2–5 different historical facts. |
| **Abstention (v1.1)** | **Hallucination Control**: Measuring the agent's ability to say "I don't know" for unplanted facts. |
| **Alias Resolution (v1.1)** | **Personalized Refs**: Mapping nicknames ("The Architect") back to formal system facts. |
| **Chronicle Conflict (v1.1)** | **Temporal Reasoning**: Resolving conflicting facts by prioritizing the most recent date/version. |

## Environment Setup & Troubleshooting

### 1. Requirements
- **Ollama**: Must be running for the **Cognitive Judge** and **Topic Detection** features.
  ```bash
  ollama serve
  ollama pull gemma4:e4b
  ```
- **Virtual Environment**: All commands must use the project `venv`.

### 2. Running the Server
The benchmark runner connects to a running ClawBrain instance. Start it in a separate terminal:
```bash
# From ClawBrain root
source venv/bin/activate
export CLAWBRAIN_URL=http://127.0.0.1:11435
python3 -m uvicorn src.main:app --host 127.0.0.1 --port 11435
```

### 3. Troubleshooting "Internal Server Error"
If you encounter `Internal error: Error finding id` in the server logs during high-volume testing:
- **Cause**: This indicates a desynchronization between the ChromaDB HNSW index and the underlying storage.
- **Solution**: The system now includes a **Phase 65 Graceful Fallback** that automatically switches to a metadata scan if index lag is detected. No manual action is required, though results may show lower "Cognitive Delta" until the index stabilizes.
- **Manual Reset**: To start from a 100% clean state:
  ```bash
  pkill -9 -f uvicorn
  rm -rf data/chroma/
  ```

## Quick Start

```bash
# 1. Generate test cases from seed libraries
python3 benchmark/run_benchmark.py generate

# 2. Setup OpenClaw profiles (Creates ~/.openclaw-benchmark-on/off)
python3 benchmark/run_benchmark.py setup-profiles

# 3. Run Tier 1 (Fast, requires ClawBrain server running)
export CLAWBRAIN_URL=http://127.0.0.1:11435
python3 benchmark/run_benchmark.py run --tier 1

# 4. Run Tier 2 (Slower, requires OpenClaw + local model gemma4:e4b)
python3 benchmark/run_benchmark.py run --tier 2

# 5. View the latest comprehensive report
python3 benchmark/run_benchmark.py report
```

---
*Generated from design/benchmark.md v1.2 / Phase 65 Update.*
