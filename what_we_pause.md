# 🦞 ClawBrain: Active Issues & Paused Tasks (April 20, 2026 - Benchmark Sync)

## ✅ Recently Resolved
- **Benchmark v1.1 Upgrade**: Successfully integrated **ATM-Bench** concepts (Alias Resolution, Chronicle Conflict, Abstention).
- **Industrial-Grade Orchestration**: `run_benchmark.py` now handles auto-cleanup and server lifecycle management.
- **100% Regression Pass (88/88)**: Core engine stability verified across all legacy and new issue-specific tests.
- **Terminology Unification (Rule 12)**: Zero instances of `context_id` remaining in the codebase.

## 📊 Benchmark v1.1 Deep Diagnosis
- **Core Strengths**: 
    - `isolation` (60%) & `chronicle` (50%): Session boundary and temporal logic are operational.
- **Critical Weaknesses**:
    - `multi_fact` (0.0%): System fails to join multiple disparate facts for a single query.
    - `noise_robust` (4.2%): Low recall in high-jargon environments. Suggests L2 thresholds are too strict.
- **Warning Signals**:
    - `Isolation Fail` in non-isolation dims: Detected data leaks likely caused by ChromaDB indexing delays or insufficient cleanup between concurrent sub-tests.
- **Behavioral Insight**:
    - `abstention` (-100%): High "hyper-enthusiasm." System prefers over-retrieving irrelevant context rather than staying silent for unknown facts.

## 📅 Plan for Tomorrow (v1.2 Focus)
1. **Recall Optimization**: 
    - Adjust L2 (Hippocampus) similarity thresholds to boost `multi_fact` scores.
    - Implement a basic **Rerank logic** to filter noise before prompt injection.
2. **Concurrency Audit**: Investigate `Isolation Fail` causes—possible need for synchronous `persist()` calls between test turns.
3. **Abstention Grounding**: Introduce "Grounding Confidence" to allow the system to decline injection if similarity is below a specific floor.

---
*Status: STABLE BUT WEAK IN MULTI-FACT REASONING. Targeting v1.2 improvements tomorrow.*
