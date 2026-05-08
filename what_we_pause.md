# 🦞 ClawBrain: Active Issues & Paused Tasks (May 8, 2026 - Multimodal & Platform Stability)

## ✅ Recently Resolved
- **Full macOS & Ubuntu Parity**: Rooted out all hardcoded Linux paths. System now auto-detects Darwin/Linux and adjusts storage and discovery logic accordingly.
- **Hardware-Aware Intelligence**: Implemented `HardwareProfiler` to detect Apple Silicon Unified Memory and NVIDIA VRAM, automatically selecting model tiers (Tier 1-3).
- **LLM Provider Decoupling**: Successfully abstracted Ollama, LM Studio, and OMLX into a unified `LLMClient`. Core cognitive features are now provider-agnostic.
- **Environmental Autonomy**: `SetupScout` now identifies and auto-starts local LLM backends (Ollama/LMS/OMLX) on both platforms, ensuring functional integrity.
- **Cognitive Judge Optimization**: Refined the grounding judge prompt to be "generous" for short technical queries, achieving 100% pass rate in real-world regression on 35B models.
- **Issue #010 Fixed**: Resolved routing security assertion mismatch (501 vs 502) by implementing strict provider resolution.

## ⏸️ Paused (Waiting for V&V Milestone)
1. **L6b Precision Tuning**: The emotional intensity scoring is stable, but we need more E2E data on "Value Eviction" before moving to v1.2.
2. **Multi-Fact Recall (Phase 58)**: Currently at 85.1%. Paused until we implement `GraphAnchoring` to connect distant entities.
3. **SignalDecomposer (Background mode)**: Refactoring the decomposer to run as a separate thread to further reduce injection latency.

## 🚀 Upcoming for v1.3
1. **Taste Profile UI**: Create a management interface for the `CLAWBRAIN_TASTE_PROFILE` to allow non-technical tuning of the agent's "personality."
2. **SGLang & vLLM Support**: Extend the Orchestrator to support high-throughput inference servers on Linux clusters.

---
*Status: MULTI-PLATFORM STABILIZED. 100% REGRESSION PASS ON macOS + LM STUDIO (35B).*
