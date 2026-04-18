# 🦞 ClawBrain: Active Issues & Paused Tasks (April 18, 2026 - Midnight Sync)

## ✅ Recently Resolved
- **Terminology Unification (Rule 12)**: Synchronized `session_id` across all Design Docs, APIs, Internal Logic, and ChromaDB schema. No more `context_id`.
- **Infrastructure Integrity**: Restored all lost `/internal/` routes and missing Hippocampus methods (`get_full_payload`, `clear_wm_state`).
- **Benchmark V18 (Toggle Mode)**: Tier 2 runner now physically manages the plugin in the Main Profile, ensuring absolute baseline purity.
- **Entity Registry (Phase 50)**: Storage layer and retrieval logic implemented. Ready for attribute-aware reasoning.
- **X-Ray View**: Dashboard now displays real-time context injection for active sessions.

## 🛑 Current Status & Blockers
- **Tier 2 Qwen Evaluation**: Running in background (`tier2_qwen_toggle_final.log`). Current Case: `[1/30]`. 
- **Regression Suite**: Last run had 17 failures (mostly logic/timing). Latest fixes to `WorkingMemory` and `storage.py` schema need a full re-verification.
- **Entity Pulse**: The LLM-based background extractor for the Registry is implemented but not yet activated to avoid VRAM contention during Tier 2.

## 📅 Plan for Tomorrow
1. **Verify Regression**: Run `./run_regression.sh` first thing. Aim for 100% green.
2. **Audit Multi-Fact**: Check if Qwen 3.6 + Topic Grouping has broken the 0.0% score barrier.
3. **Optimize Distillation**: Fix the 404 in manual trigger calls found in `test_p17`.

---
*Status: STABLE & UNIFIED. Good night!*
