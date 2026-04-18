# 🦞 ClawBrain: Active Issues & Paused Tasks (April 18, 2026)

All critical blockers from the April 17 benchmark have been **RESOLVED**.

## ✅ Recently Resolved
- **Management Dashboard**: Implemented a built-in Web UI at `/dashboard` for memory observability.
- **Tier 2 Qwen Run**: Successfully launched end-to-end evaluation using Qwen 3.6 (35b) on RTX 4090.
- **Tier 1 Isolation**: Fixed lazy hydration and added mandatory `context_id` filters.
- **High-Distance Latency**: Overhauled ChromaDB schema to remove large JSON blobs from metadata.
- **Cross-Platform Paths**: Refactored OpenClaw profile logic to support both MacOS and Linux.
- **Recursive Summarization**: Implemented stateful knowledge merging in Neocortex (Phase 40).
- **Baseline Integrity**: Stabilized Tier 1 "OFF" baseline at 0.0%.

## 🛑 Current Paused Tasks
- **Tier 2 Evaluation Progress**: Monitoring the 30-case run. Average case time: ~45 mins.
- **Multi-Fact Synthesis**: Tier 1 score is still 0.0%. Added grouping logic in Router; awaiting Tier 2 results to see if Qwen 3.6 can synthesize better than Gemma 4.

---
*Status: STABLE. Ready for Tier 2 evaluation.*
