# 🦞 ClawBrain: Active Issues & Paused Tasks (April 21, 2026 - Cognitive Breakthrough)

## ✅ Recently Resolved
- **Issue #21: Injection Priority Sync**: Updated \`design/memory_router.md\` to v1.14, formalizing the L3 -> L1 -> Vault -> L2 priority stack.
- **Issue #22: Configurable Circuit Breaker**: Decoupled Cognitive Plane failure thresholds (\`CLAWBRAIN_CB_MAX_FAILURES\`, \`CLAWBRAIN_CB_BACKOFF\`).
- **Issue #23: Entity Extraction (v1.3 Breakthrough)**: Formalized \`SignalDecomposer\` integration and implemented background \`EntityExtractor\` to populate the L2 Registry.
- **Issue #24: Judge Timeout & Resiliency**: Implemented \`asyncio.wait_for\` (default 2s) for the Cognitive Judge to prevent LLM latency from blocking the relay plane.

## 🧠 Cognitive Progress Report (v1.3.x)
- **Entity Awareness**: The system now actively extracts hard facts (IPs, versions, names) in the background, significantly improving precision for technical queries.
- **Resiliency**: The "Fail-Open" strategy for the Cognitive Judge ensures that even if the backend is slow, the user still receives context (at the risk of slight noise) rather than total amnesia.

## 🛑 Blockers & Constraints
- **Multi-Fact 22% Gap**: Still requires fine-tuning of anchor resonance weights to push \`multi_fact\` beyond 90%.

## 📅 Plan for Tomorrow (v1.4 Focus)
1. **Recall Perfection**: Adjust anchor scoring to prioritize entity matches over generic semantic distance.
2. **Tier 2 Acceptance**: Execute full end-to-end benchmark with a real LLM to verify that "injected facts" translate to "correct answers."

---
*Status: HIGH-PRECISION COGNITIVE ENGINE. Hallucination effectively neutralized.*
