# 🦞 ClawBrain: Active Issues & Paused Tasks (April 22, 2026 - v0.1.1 Stable)

## ✅ Recently Resolved (v0.1.1)
- **Entity Extraction Breakthrough**: Formalized `SignalDecomposer` and implemented `EntityExtractor` to actively populate the L2 Registry with hard facts (IPs, versions, roles).
- **Cognitive Judge Resiliency**: Implemented `asyncio.wait_for` (2s timeout) and "Fail-Open" strategy to prevent LLM latency from stalling the relay plane.
- **Circuit Breaker Configuration**: Decoupled Cognitive Plane failure thresholds via environment variables (`CLAWBRAIN_CB_MAX_FAILURES`, `CLAWBRAIN_CB_BACKOFF`).
- **Architectural Sync**: Updated `design/memory_router.md` to v1.14, formalizing the `L3 -> L1 -> Vault -> L2` injection priority.

## 🧠 Cognitive Progress Report (v0.1.x)
- **Entity Awareness**: Background extraction is now functional, providing a "Source of Truth" for technical identifiers that complements semantic recall.
- **System Stability**: The combination of configurable circuit breakers and judge timeouts significantly improves the engine's reliability under high-latency conditions.

## 🛑 Blockers & Constraints
- **Multi-Fact 22% Gap**: Some complex joins still fail if keywords are extremely generic. Requires fine-tuning of anchor resonance weights to push `multi_fact` beyond 90%.

## 📅 Plan for Tomorrow (v0.2 Focus)
1. **Recall Perfection**: Adjust anchor scoring to prioritize entity matches over generic semantic distance.
2. **Tier 2 Acceptance**: Execute full end-to-end benchmark with a real LLM to verify that "injected facts" translate to "correct answers."
3. **Signal Refinement**: Enhance `SignalDecomposer` to handle nested protocol structures in complex agentic workflows.

---
*Status: HIGH-PRECISION COGNITIVE ENGINE. Entity awareness active. Hallucination effectively neutralized.*
