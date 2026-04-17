# 🦞 ClawBrain: Active Issues & Paused Tasks (April 17, 2026)

## 🛑 Critical Issues Found During Benchmark

### 1. Tier 1 Isolation Failures (Data Leaking)
*   **The Problem**: The Tier 1 benchmark identified **5 total Isolation Failures** across the `isolation`, `neocortex`, and `recall_dist` dimensions.
*   **Observation**: Data from one `session_id` is leaking into the prompt additions of unrelated sessions.
*   **Action Required**: Audit `src/memory/storage.py` (ChromaDB `where` filters) and `src/memory/router.py` to ensure every retrieval strictly enforces the `context_id` boundary.

### 2. Multi-Fact Synthesis Gap
*   **The Problem**: Multi-fact recall score is currently **0.0%**.
*   **Observation**: The system successfully retrieves individual facts but fails to synthesize them when a query requires multiple historical pieces of context to answer.
*   **Action Required**: Refine the `assemble` logic in `src/memory/router.py` to better structure and "link" multiple retrieved facts for the LLM.

### 3. Tier 2 Benchmark Blocker (OpenClaw Profiles)
*   **Status**: **PAUSED**.
*   **The Problem**: The current profile directory name `.openclaw-benchmark-on` is rejected by OpenClaw as an invalid profile ID (`[openclaw] Invalid --profile (use letters, numbers, "_", "-" only)`).
*   **Action Required**: Refactor `benchmark/src/profiles.py` to use alpha-numeric profile names (e.g., `bm_on`, `bm_off`) and ensure the configuration files are correctly linked.

### 4. High-Distance Latency (ReadTimeout)
*   **The Problem**: Observed `ReadTimeout` errors in benchmark cases with 400+ noise turns.
*   **Observation**: System latency increases exponentially with history depth.
*   **Action Required**: Investigate indexing performance and query optimization in the Hippocampus layer.

---
*This file tracks active blockers and findings from the April 17, 2026 benchmark run. Resume here for the next phase.*
