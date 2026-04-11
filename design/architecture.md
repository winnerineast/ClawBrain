# design/architecture.md v1.1

## 1. Project Vision
ClawBrain is more than a gateway — it is a universal LLM enhancement engine with "brain-like memory" capabilities.

## 2. Core System Modules

### Modules A, B, C (Gateway & Optimizer)
[Accepted and complete]

### Module D: Third-Generation Neural Memory Engine
- **Hippocampus**: Episodic memory. A write-once system keyed by time with semantic vector retrieval via ChromaDB.
- **Neocortex**: Semantic memory. Slow-integration distillation with async background workers.
- **Working Memory**: Active cache. Priority queue driven by Attractor dynamics with rapid decay.

## 3. Reliability & Robustness: Dual-Channel Isolation
To ensure high availability and non-blocking performance, ClawBrain employs **Network Plane Isolation**:
1. **The Relay Plane**: A high-concurrency HTTP client dedicated solely to upstream LLM traffic. This plane is performance-optimized and has strict isolation from internal tasks.
2. **The Cognitive Plane**: An independent, internal HTTP client owned by the `MemoryRouter`. It handles background "thinking" tasks (Room Detection, Fact Distillation) without competing for the Relay Plane's connection pool or bandwidth.

## 3. Implementation Roadmap (Updated)
- **Phase 1–5**: Core gateway and protocol stack [Complete]
- **Phase 6–11**: Neural memory system development [Launched]
- **Phase 12**: Final integration and production mounting
