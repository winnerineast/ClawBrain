# 🦞 ClawBrain: Active Issues & Paused Tasks (April 22, 2026 - v0.2.0 Dev)

## ✅ Recently Resolved (v0.2.0 Breakthrough)
- **The Breathing Brain**: Decoupled cognitive processing from the relay plane using an autonomous background heartbeat loop (`CLAWBRAIN_HEARTBEAT_SECONDS`).
- **Thought-Retriever Framework**: Implemented granular "Thought" extraction in Neocortex with **Root Source Mapping** (mapping high-level insights back to raw L2 traces).
- **Near-Zero Latency Assembly**: Refactored `get_combined_context` into a strict read-only pipeline, eliminating the synchronous Cognitive Judge for pre-verified thoughts.
- **Root Source Resolver**: Added batch retrieval of full payloads in Hippocampus to provide grounded evidence for every retrieved thought.

## 🧠 Cognitive Progress Report (v0.2.x)
- **Duality of Process**: The system now has a distinct "Foreground Reflex" (On-demand context) and "Background Meditation" (Heartbeat distillation).
- **Factual Grounding**: By injecting raw evidence alongside distilled thoughts, we've significantly increased the model's ability to cross-reference facts without hallucination.

## 🛑 Blockers & Constraints
- **Thought Deduplication**: The heartbeat loop currently appends thoughts; we need a "Merging" logic in Neocortex to prevent duplicate insights over long sessions.
- **Multi-Fact 22% Gap**: The Thought-Retriever approach addresses this, but we need an end-to-end benchmark to confirm the new F1 score.

## 📅 Plan for Tomorrow (v0.3 Focus)
1. **Thought Consolidation**: Implement a "Thought Merging" worker that collapses similar insights and updates confidence scores.
2. **Tier 1 Verification**: Execute full AcademicEval-style benchmark to quantify the gain from Root Source Mapping.
3. **Registry Hardening**: Ensure Entity extraction and Thought extraction don't collide when updating the L2 metadata.

---
*Status: DUAL-PROCESS COGNITIVE ENGINE. Breathing active. Thoughts grounded in evidence.*
