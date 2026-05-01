# 🦞 ClawBrain: Active Issues & Paused Tasks (May 1, 2026 - Multi-Platform Stability & Phase 65 Fix)

## ✅ Recently Resolved
- **Multi-Platform Config Sync**: Implemented a robust `get_env()` system supporting `DARWIN_` and `LINUX_` prefixes in a single `.env` file, enabling seamless switching between macOS and Ubuntu.
- **Phase 65 Stability Fix**: Resolved the "Error finding id" ChromaDB exception through a graceful metadata-fallback mechanism when HNSW index lag is detected.
- **v1.2 Architectural Alignment**: Updated high-level architecture diagrams and documentation to reflect the Ingress Layer (HTTP/MCP/CLI) and Knowledge Vault (Ext) integration.
- **Constitutional Compliance (Rule 4)**: Purged all "Traceability Violations" by ensuring every source file (CLI, MCP, etc.) properly cites its design specification.
- **Refined Documentation (EN/CN)**: Fully synchronized multi-language READMEs with simplified, ultra-compatible Mermaid diagrams and installation notes.
- **Historical Cleanup**: Merged all transient prompt/task files into authoritative design documents and purged legacy logs/benchmark results.

## 🛑 Current Status
- **Tier 1 Direct Run**: Functionally stable after Phase 65 fix. 100% pass in Fact Evolution and Neocortex.
- **ChromaDB Resilience**: The system now survives high-concurrency write/read bursts during benchmarking without 500 errors.
- **GitNexus Intelligence**: Index refreshed with **2,068 symbols** and **3,549 relationships**, providing high-fidelity maps for AI agents.

## 🚀 Next Priorities
1. **Tier 2 E2E Verification**: Execute full end-to-end cycles using the `gemma4:e4b` model to verify cognitive recall at the response level.
2. **Context Compression**: Implement L1/L2 deduplication for tight context windows (<1000 chars).
3. **Hybrid Retrieval (v1.11)**: Combine semantic vector search with exact keyword matching to improve recall for IDs, Ports, and Tokens.

---
*Status: MULTI-PLATFORM PRODUCTION READINESS. Infrastructure and Stability Layer stabilized.*
