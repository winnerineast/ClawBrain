# Task: Generic Intelligence & Multi-Fact Breakthrough

## Objective
Enhance ClawBrain to support generic cross-platform operation (macOS/Ubuntu) and resolve the 22% multi-fact recall gap. Achieve stable high-precision retrieval across diverse datasets.

## Requirements
1. **Cross-Platform Portability**:
   - Support `omlx` provider for macOS.
   - Robust `.env` generation with quoted values for shell compatibility.
   - OS-agnostic path handling in setup utilities.
2. **Entity-Aware Signaling (v1.9)**:
   - Upgrade `SignalDecomposer` to extract compound proper nouns and technical anchors.
   - Implement a background Fact Registry in `Hippocampus` to store verified facts.
3. **Judge-Centric Admission (v1.4)**:
   - Replace rigid similarity thresholds with a "Wide Net" pre-filter.
   - Leverage reasoning-aware LLMs for final cognitive verification.
4. **Fact Evolution**:
   - Enable overriding of historical facts in the registry when updated information is detected.

## Verification
- 100% Pass on Full Regression Suite.
- >85% Multi-Fact Recall on Tier 1 Benchmark.
- Verified isolation on macOS and Ubuntu.

## Header
/* Generated-by: 20260427-GENERIC-INTELLIGENCE */
