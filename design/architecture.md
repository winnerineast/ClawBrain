# design/architecture.md v1.2 (Phase 56 - v0.2.0)

## 1. Project Vision
ClawBrain is more than a gateway — it is a universal LLM enhancement engine with "brain-like memory" capabilities.

## 2. Dual-Process Cognitive Architecture (The Breathing Brain)
Inspired by the Thought-Retriever framework, ClawBrain v0.2 split memory operations into two decoupled rhythms:

### 2.1 The Foreground Reflex (On-Demand Context)
- **Rhythm**: Triggered by user request.
- **Responsibility**: Instantaneous context assembly.
- **Constraint**: **Strict Read-Only**. It must not trigger any LLM calls or heavy processing.
- **Logic**: Retrieve granular "Thoughts" from Neocortex and immediately pull "Root Evidence" from Hippocampus.

### 2.2 The Background Breathing (Heartbeat Loop)
- **Rhythm**: Autonomous heartbeat (default 30s).
- **Responsibility**: Memory digestion, Entity Extraction, Thought Distillation.
- **Constraint**: Self-paced via `CircuitBreaker`. It operates on the **Cognitive Plane**.

## 3. Core System Modules

### Module D: Neural Memory Engine
- **Hippocampus (L2)**: Episodic memory. Permanent interaction traces + Root Source Mapping (Trace ID indexing).
- **Neocortex (L3)**: Semantic memory. Extracts granular "Thoughts" (Insights) instead of monolithic summaries.
- **Working Memory (L1)**: Short-term cache. Priority queue driven by Attractor dynamics with rapid decay.

## 4. Reliability & Robustness: Dual-Channel Isolation
ClawBrain employs strict **Plane Isolation**:
1. **The Relay Plane**: High-concurrency HTTP client for upstream traffic.
2. **The Cognitive Plane**: Independent, internal client for background tasks (Room Detection, Thought Extraction).

## 5. Implementation Roadmap (Updated)
- **Phase 1–11**: Neural memory core [Complete]
- **Phase 12**: v0.1.1 Entity Awareness [Complete]
- **Phase 56**: v0.2.0 Thought-Retriever & Breathing Brain [Complete]
- **Phase 60**: v0.3.0 Thought Consolidation & Merging [Planned]
