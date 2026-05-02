# design/architecture.md v1.2

## 1. Project Vision
ClawBrain is more than a gateway — it is a universal LLM enhancement engine with "brain-like memory" capabilities.

## 2. Core System Modules

### 2.1 Ingress Layer (Interfaces)
- **HTTP Relay (`main.py`)**: Transparent OpenAI-compatible API proxy with memory injection.
- **MCP Server (`mcp_server.py`)**: Model Context Protocol implementation for modern agent integration.
- **Admin CLI (`cli.py`)**: Scriptable interface for manual memory management and ingestion.

### 2.2 Neural Memory Engine (Core)
- **Value Modulation (L6b)**: The Precision Layer. A pre-ingestion filter that scores interactions for emotional intensity, intent, or structural importance, aggressively decaying or dropping low-value chatter before it reaches long-term storage.
- **Hippocampus (L2)**: Episodic memory. A write-once system keyed by time with semantic vector retrieval via ChromaDB, storing only high-value interactions that pass the L6b filter.
- **Neocortex (L3)**: Semantic memory. Slow-integration distillation with async background workers, protected by **TasteGuard** to prevent subjective beliefs from being overwritten.
- **Working Memory (L1)**: Active cache. Priority queue driven by Attractor dynamics with rapid decay.
- **Knowledge Vault (Ext)**: Incremental Obsidian vault indexing providing "Subjective Curvature" (a Normal field) to prioritize personal truth over statistical averages.

## 3. Reliability & Robustness: Dual-Channel Isolation
To ensure high availability and non-blocking performance, ClawBrain employs **Network Plane Isolation**:
1. **The Relay Plane**: A high-concurrency HTTP client dedicated solely to upstream LLM traffic. This plane is performance-optimized and has strict isolation from internal tasks.
2. **The Cognitive Plane**: An independent, internal HTTP client owned by the `MemoryRouter`. It handles background "thinking" tasks (Room Detection, Fact Distillation, Vault Indexing) without competing for the Relay Plane's connection pool or bandwidth.

## 4. Implementation Roadmap (Updated)
- **Phase 1–5**: Core gateway and protocol stack [Complete]
- **Phase 6–11**: Neural memory system development [Complete]
- **Phase 12**: Knowledge Vault & MCP Integration [Complete]
- **Phase 13**: Final integration and production mounting [Current]
