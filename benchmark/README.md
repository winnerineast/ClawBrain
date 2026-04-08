# ClawBrain Benchmark: Quantifying the Cognitive Delta

[中文版](./README_CN.md)

## Why Benchmark?

LLM memory is notoriously difficult to measure. Unit tests can confirm that code doesn't crash, and logs can show that data is being saved, but they cannot answer the most critical question: **Does this actually make the AI smarter?**

ClawBrain's value is defined by the **Delta**—the measurable improvement in an agent's ability to recall facts and maintain context over time compared to a standard, stateless LLM interaction. This benchmark suite provides the objective evidence required to prove that value.

## The Two-Tiered Validation Strategy

To ensure both technical precision and real-world utility, the benchmark is split into two tiers:

### Tier 1: Infrastructure Integrity (Direct API)
*   **Method**: Drives ClawBrain’s `/internal/*` endpoints directly, bypassing the LLM.
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

## Quick Start

```bash
# 1. Generate test cases from seed libraries
python3 benchmark/run_benchmark.py generate

# 2. Setup OpenClaw profiles (Creates ~/.openclaw-benchmark-on/off)
# This command configures contextEngine to 'clawbrain' for 'on' and 'legacy' for 'off'
python3 benchmark/run_benchmark.py setup-profiles

# 3. Run Tier 1 (Fast, requires ClawBrain server running)
PYTHONPATH=. ./venv/bin/python3 benchmark/run_benchmark.py run --tier 1

# 4. Run Tier 2 (Slower, requires OpenClaw + local model gemma4:e4b)
# Uses profiles in ~/.openclaw-benchmark-on and ~/.openclaw-benchmark-off
PYTHONPATH=. ./venv/bin/python3 benchmark/run_benchmark.py run --tier 2

# 5. View the latest comprehensive report
python3 benchmark/run_benchmark.py report
```

## Tier 2 Environment Details

To ensure a clean testing environment, Tier 2 uses dedicated OpenClaw profiles and workspaces:

- **Profiles**:
  - `benchmark-on`: Located at `~/.openclaw-benchmark-on/`, uses ClawBrain as the `contextEngine`.
  - `benchmark-off`: Located at `~/.openclaw-benchmark-off/`, uses the legacy `contextEngine`.
- **Workspaces**:
  - `benchmark-on` uses `~/.openclaw/workspace-benchmark-on`.
  - `benchmark-off` uses `~/.openclaw/workspace-benchmark-off`.
- **Default Model**: The benchmark defaults to `ollama/gemma4:e4b`. Ensure this model is pulled in Ollama before running.


## Work Daily (Phase 32 Status)

The core infrastructure and Tier 1 integrity tests are now fully verified. The next immediate focus is executing **Tier 2 (Cognitive Effectiveness)** benchmarks. This will quantify the end-to-end recall rate of the `gemma4:e4b` model when enhanced by ClawBrain's tri-layer memory system.

**Next Tasks:**
1.  Verify `gemma4:e4b` is locally active in Ollama.
2.  Execute full Tier 2 run: `python3 benchmark/run_benchmark.py run --tier 2`.
3.  Analyze the "Cognitive Delta" between `benchmark-on` and `benchmark-off` profiles.

---
*This benchmark is a living system. As ClawBrain evolves (e.g., adding Vector Embeddings), these metrics provide the guardrails to ensure every "improvement" is a genuine cognitive gain.*
