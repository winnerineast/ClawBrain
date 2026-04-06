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
python benchmark/run_benchmark.py generate

# 2. Run Tier 1 (Fast, requires ClawBrain server running)
python benchmark/run_benchmark.py run --tier 1

# 3. Run Tier 2 (Slower, requires OpenClaw + local model)
python benchmark/run_benchmark.py run --tier 2

# 4. View the latest comprehensive report
python benchmark/run_benchmark.py report
```

---
*This benchmark is a living system. As ClawBrain evolves (e.g., adding Vector Embeddings), these metrics provide the guardrails to ensure every "improvement" is a genuine cognitive gain.*
