# ISSUE-002: Benchmark Quality Audit & Cognitive Performance Gap

## Status: OPEN 🔴
**Priority**: HIGH
**Date**: April 6, 2026

## 1. Overview
This report documents the results of the Phase 26/27 Benchmark execution, identifying critical performance gaps in the Neocortex (L3) layer and reliability issues in the Tier 2 (E2E) execution pipeline.

## 2. Test Environment & Data
- **Seed Data**: 110 atomic facts (`data/facts/`) and 90 noise dialogues (`data/noise/`).
- **Test Cases**: 134 structured scenarios generated via `generate.py`.
- **Dimensions**:
    - `recall_dist`: Long-term memory across 5-200 turns of noise.
    - `fact_evol`: Tracking updates to previously known facts.
    - `isolation`: Cross-session data leakage prevention.
    - `multi_fact`: Simultaneous retrieval of multiple independent facts.
    - `noise_robust`: Retrieval under high-intensity background noise.
    - `neocortex`: Semantic summary-based retrieval.

## 3. Benchmark Results (Baseline Tier 1)

| Dimension | OFF (Baseline) | ON (ClawBrain) | Delta | Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **Fact Evolution** | 0.0% | 100.0% | +100.0% | Excellent |
| **Isolation** | 0.0% | 100.0% | +100.0% | Secured |
| **Recall Distance** | 0.0% | 43.8% | +43.8% | Moderate |
| **Multi-fact** | 0.0% | 25.3% | +25.3% | Poor |
| **Noise Robustness**| 0.0% | 8.3% | +8.3% | Critical |
| **Neocortex (L3)** | 0.0% | 0.0% | +0.0% | **Failed** |

## 4. Identified Problems

### 4.1 Neocortex (L3) Retrieval Failure
- **Issue**: 0% recall in Neocortex dimension.
- **Root Cause**: `router.py` injects a default string `"No historical summary."` when L3 is empty. This adds noise to the prompt and fails the `must_contain` keyword audit. Additionally, async distillation via Ollama is too slow for the benchmark's rapid-fire ingestion.

### 4.2 L2 (Hippocampus) Format Noise
- **Issue**: Poor performance in `noise_robust` and `multi_fact`.
- **Root Cause**: Memory traces are injected as raw JSON objects. This is token-inefficient and increases cognitive load for the model, leading to retrieval failures in dense contexts.

### 4.3 Tier 2 Execution Reliability (OpenClaw Integration)
- **Issue**: "Extra data" and "No valid JSON" errors during OpenClaw E2E runs.
- **Root Cause**: OpenClaw stderr contains a mix of ANSI-colored logs, plugin warnings, and multiple JSON objects. The original regex-based extraction was too brittle to handle this noise.
- **Status**: Partially mitigated by improved regex and extended 1200s timeouts.

### 4.4 Prompt Bloating
- **Observation**: OpenClaw's own system prompt + workspace context often exceeds 30,000 characters. Adding ClawBrain memory on top causes focus loss or model "forgetting" in Tier 2 scenarios.

## 5. Remediation Plan

### Phase 29: Neocortex Silence (High Priority)
- Update `src/memory/router.py` to remain silent (inject nothing) if no L3 summary is found.
- Implement a blocking `/internal/compact` mode for benchmarking to ensure distillation completes before evaluation.

### Phase 30: Plain-Text Hippocampus
- Refactor `MemoryRouter` to inject L2 memories as flat, human-readable text bullet points instead of JSON.
- Example: `[Fact] 2026-04-06: The server uses PostgreSQL 15.2.`

### Phase 31: Context Budgeting v2
- Implement more aggressive token trimming for OpenClaw-integrated runs.
- Prioritize L1 (Working Memory) over L2 (Hippocampus) based on semantic similarity scores rather than just chronological order.

## 6. Verification Plan
1. Re-run Tier 1 after Phase 29/30 to verify Neocortex recall.
2. Execute full Tier 2 marathon with the new 1200s timeout and verbosity logs.
3. Compare ON vs OFF in Tier 2 to measure the "Cognitive Delta" in a real-world stack.
