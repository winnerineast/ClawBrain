# design/memory.md v1.8

## 1. Objective
Generate the **ClawBrain Neural Memory System**. This system achieves symmetric storage of interactions, fault tolerance, signal denoising, and defence against high-volume data bursts through a three-layer memory architecture.

## 2. Architecture & Logic

### 2.1 Interaction State Machine
- **Two-phase commit model**:
  - `PENDING` (STIMULUS_RECEIVED): Initialised when input is received.
  - `COMMITTED` (REACTION_COMPLETED): Associated and solidified when output is received.
  - `ORPHAN` (INCOMPLETE_INTENT): Any input with no response after 300 seconds.
- **Atomic unit**: `InteractionTrace` object — stimulus and reaction must always be stored as a pair `(Stimulus, Reaction)`.

### 2.2 Signal Decomposer
- **Schema Fingerprinting**: Identifies repeated protocol templates by computing an MD5 hash of the request structure (excluding message content).
- **Core Intent Extraction**: Precisely extracts the text content of the last `role: user` entry from the `messages` array.

### 2.3 Storage Layers & Lifecycle
- **Working Memory (L1)**: In-memory `OrderedDict` with time-constant-based weight decay.
- **Hippocampus (L2)**: Lossless SQLite FTS5 storage. Single payloads > 512 KB are streamed to disk.
- **Neocortex (L3)**: Background semantic summarisation and rule generalisation.

## 3. Test & Audit Specification (TDD)

### 3.1 Mandatory Verification Points
- **State transitions**: Verify correct progression from `PENDING` to `COMMITTED`.
- **Orphan detection**: Verify timed-out records are marked as `ORPHAN`.
- **Signal audit**: Verify `SignalDecomposer` produces consistent hashes for identical structures, and correctly extracts user intent.

### 3.2 Audit Log Standard
- Follow the **Rule 3** Side-by-Side layout.
- Logs must display: `Raw Payload → Fingerprint → Extracted Intent`.

## 4. Output Targets
- `src/memory/signals.py`: Signal decomposition and fingerprinting.
- `tests/test_p6_memory_resilience.py`: Full tests covering the state machine and signal audit.
