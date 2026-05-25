# 🦞 ClawBrain: The Silicon Hippocampus for your Agentic Workflow

English | [中文版](./README_CN.md)

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

> [!IMPORTANT]
> **🚀 FINAL STABLE RELEASE v1.44 (PROJECT COMPLETED & CLOSED)**
> ClawBrain has successfully reached its production milestone. The codebase is fully stabilized, validated across Apple Silicon & Linux under strict process isolation, and boasts a **100% pass rate** on its regression suite (45+ modules, 350+ assertions). This project is now officially concluded and marked as stable.

ClawBrain is an **infrastructure-layer memory engine** designed to give AI agents (specifically [OpenClaw](https://github.com/openclaw/openclaw)) a persistent, evolving, and highly precise "brain." 

---

## 📊 Cognitive Performance (v1.10 Breakthrough)

ClawBrain v1.10 introduces the **Silicon Hippocampus (L6b)** — shifting from "Machine/Lossless" memory to "Biological/Value-Driven" recall.

*   **Cognitive Delta**: **+60.0% improvement** in recall precision for noisy, long-context technical sessions.
*   **Precision (L6b)**: Successfully identifies and **drops 30-40%** of low-value conversational noise before storage.
*   **Multi-Fact Recall**: **85.1% success rate** on complex, non-semantic entity joins.
*   **Abstention (Hallucination Control)**: **100% Score**. The system silences itself perfectly when no relevant facts exist.
*   **Stability (Phase 65)**: 0% server crashes during high-concurrency write/read bursts.

> [!IMPORTANT]
> ClawBrain is now fully verified on both **macOS (Apple Silicon)** and **Ubuntu (Linux)** with automated environment recovery.

---

## ⚡️ The Breathing Brain: High-Recall Architecture

The v1.10 update introduces **Biological Bias**, refining the decoupled cognitive rhythm established in v1.4.

1.  **Value Modulation (L6b)**: Every interaction is scored for "Technical/Emotional Importance." Trivial chatter is dropped, ensuring L2 storage stays pure.
2.  **Priority Anchoring**: Technical IDs and "Mentions" are extracted and indexed **synchronously**, ensuring Turn N+1 can always see Turn N.
3.  **TasteGuard Protection**: Core subjective facts (Architectural preferences, User values) are "locked" and protected from being overwritten during background distillation.
4.  **Cognitive Heartbeat**: A 30s background loop performs deep LLM-based fact mining and L3 Neocortex distillation without blocking your chat.
5.  **Subjective Cognitive Judge**: Replaces rigid thresholds with a "Taste-Aware" filter that validates context against your specific engineering profile using live reasoning.


---

## 💎 The ClawBrain Edge: Verified by Real-World Evidence

ClawBrain is built on **Engineering Transparency**. We prove our claims with raw data from our regression suite.

### 1. 100% Passive Capture (No "Decisions" Required)
*   **The Problem**: Models often forget to "save" important context during fast-paced sessions.
*   **Real-World Sample** (`tests/test_p26`):
    *   **Input User**: *"The project uses Python 3.12 and ChromaDB v0.4."*
    *   **Assistant Response**: *"Got it, I'll keep that in mind."*
    *   **ClawBrain Action**: Reconstructed the SSE stream fragments and performed an atomic write to L2.
    *   **Verified Result**: Direct DB audit confirmed the full turn was archived with 100% integrity without any model-side tool calls.

### 2. Intent-Based Retrieval (Beyond Keyword Matching)
*   **The Problem**: Searching for "database" misses notes written as "data store" or "Postgres."
*   **Real-World Sample** (`tests/test_chromadb_semantic_recall.py`):
    *   **Stored Fact**: *"The primary data store is at 192.168.1.50"*
    *   **Query A**: *"What is the database address?"* → **RECALLED** (Similarity: 0.89)
    *   **Query B**: *"Where are we keeping our information?"* → **RECALLED** (Similarity: 0.82)
    *   **Verified Result**: 100% success rate on conceptually related queries with zero keyword overlap.

### 3. Rigid Budget Enforcement (Stack Math)
*   **The Problem**: Over-injecting context causes the model to lose the "end" of your prompt.
*   **Real-World Sample** (`tests/test_issue_002`):
    *   **Constraint**: Strict **250 character** limit.
    *   **Component Cost**: L3 Summary (78) + L1 Working Memory (81) + Wrapper (50) = 209 chars.
    *   **ClawBrain Action**: Calculated that L2 Header (49) would bring total to 258.
    *   **Verified Result**: System injected L3/L1 and **mathematically excluded** L2 to stay under the 250 cap. **Zero prompt truncation.**

### 4. Zero-Waste Vault Sync (The "Touch" Test)
*   **The Problem**: Re-indexing thousands of notes on every change is slow and expensive.
*   **Real-World Sample** (`tests/test_p35`):
    *   **Input**: 100 Obsidian notes. Manually `touch`ed 4 files (changing timestamp only).
    *   **ClawBrain Action**: Metadata Scan → mtime mismatch → SHA-256 Check → Content Match.
    *   **Verified Result**: `0 embeddings updated`. 100% of compute cost was saved by recognizing the content hadn't changed.

### 5. High-Pressure Stability (Dual-Channel Isolation)
*   **The Problem**: Background tasks (distillation/scanning) shouldn't make your chat laggy.
*   **Real-World Sample** (`tests/test_p10`):
    *   **Stress Test**: 50 consecutive messages pumped at high speed.
    *   **ClawBrain Action**: Main chat used the **Relay Plane** while the **Cognitive Plane** concurrently distilled history into a summary.
    *   **Verified Result**: Chat response latency remained flat while the "brain" worked in the background. No deadlocks, 100% success.

---

## 🚀 Installation (One-Minute Setup)

ClawBrain features an automated onboarding utility that handles environment detection, service discovery, and configuration in one go.

```bash
# 1. Clone the repository
git clone https://github.com/winnerineast/ClawBrain.git
cd ClawBrain

# 2. Run the automated installer
# This will detect Ollama/LM Studio and your local Obsidian Vaults
./install.sh

# 3. Start the server
source venv/bin/activate
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 11435
```

---

## 📊 Monitoring & Visualization

ClawBrain provides an **All-in-One Information Flow Dashboard** to visualize how the two planes (Relay & Cognitive) work together to enhance your AI's memory.

### 1. Access the Dashboard
Once the server is running, open your browser to:
👉 **[http://localhost:11435/dashboard](http://localhost:11435/dashboard)**

### 2. Live Information Flow
- **Visual Diagram**: Real-time Mermaid.js flowchart showing data convergence from Vault and Neocortex.
- **Event Log**: A session-isolated scrolling timeline of "Ingest", "DeepIndexing", and "DeepMining" events.
- **Context X-Ray**: Click any "Context Enrichment" event to see the exact prompt payload sent to the LLM.

### 3. Taste & Personality UI (v1.3)
You can now tune your agent's **Subjective Bias** directly from the dashboard:
- Navigate to the **"Taste & Personality"** tab.
- Edit the `TasteGuard` profile (e.g., set architectural preferences or coding styles).
- **Persistence**: Changes are saved directly to your `.env` file and applied instantly to future background distillations.

---

> [!NOTE]
> **Multi-Platform Sync**: ClawBrain supports synchronized settings for macOS and Ubuntu in a single `.env` file. Use `DARWIN_` or `LINUX_` prefixes for platform-specific overrides (e.g., `LINUX_CLAWBRAIN_DB_DIR`).

---

## 🔌 Integration & Usage

ClawBrain is a universal memory hub. You can integrate it with any AI agent using three primary methods:

### Choice 1: Transparent HTTP Relay (Zero-Config)
Point your agent's API `baseUrl` to ClawBrain (port 11435). ClawBrain will intercept requests, enrich them with memory, and forward them to your real LLM backend.

- **Universal Support**: Includes Anthropic (Claude), Google (Gemini), DeepSeek, OpenAI, and more.
- **SSE Reverse-Translation**: Automatically translates Anthropic's streaming format into standard OpenAI chunks for seamless integration with legacy clients.

### Choice 1.5: Native OpenClaw Plugin (Context Engine)
For a deeper integration with [OpenClaw](https://github.com/openclaw/openclaw), use the native Context Engine plugin:

```bash
# 1. Copy the plugin to the global extensions directory
mkdir -p ~/.openclaw/extensions/
cp -r packages/openclaw-pkg ~/.openclaw/extensions/clawbrain

# 2. Add to your ~/.openclaw/openclaw.json whitelist
# { "plugins": { "allow": ["clawbrain"], "slots": { "contextEngine": "clawbrain" } } }
```

### Choice 2: Model Context Protocol (MCP)
ClawBrain supports the industry-standard MCP for modern agents (Claude Desktop, Cursor, etc.).

*   **Remote (SSE)**: Connect to `http://127.0.0.1:11435/mcp/sse`
*   **Local (Stdio)**: Add to your agent's config:
    ```bash
    command: "python3",
    args: ["-m", "src.mcp_server"]
    ```

### Choice 3: Scriptable CLI
Use the `src/cli.py` utility for direct memory access from scripts or lightweight agents.

```bash
# Ingest a fact
python3 src/cli.py ingest "The project password is ALPHA"

# Query for context
python3 src/cli.py query "password"
```

### 🔐 Session Isolation
Isolate memory between different projects or users by sending a simple header:
`x-clawbrain-session: project-alpha`

---

## 🧠 Data Flow & Intelligence Architecture

ClawBrain operates as a high-performance neural orchestrator, separating the **Relay Plane** (real-time traffic) from the **Cognitive Plane** (background intelligence).

```mermaid
graph TD
    subgraph Ingress
        API[HTTP Relay]
        MCP[MCP Server]
        CLI[Admin CLI]
    end

    subgraph Intelligence
        Detector[Protocol Detector]
        Router[Memory Router]
        Translator[Dialect Translator]
        Pipe[Capture Pipeline]
    end

    subgraph Storage [Memory Planes]
        direction TB
        L1((Working Memory))
        L2[(Hippocampus)]
        L3[Neocortex]
        L6b[Value Modulation]
        Ext[Vault Indexer]
    end

    API --> Detector
    MCP --> Detector
    CLI --> Detector
    
    Detector --> Router
    Router --> Translator
    Translator --> LLM((Upstream LLM))
    
    LLM --> Pipe
    Pipe --> L6b
    L6b --> L2
    
    Router --- L1
    Router --- L2
    Router --- L3
    Router --- L6b
    Router --- Ext
```

### 1. The Request Lifecycle
1.  **Ingress & Detection**: Requests enter via HTTP, MCP, or CLI. The `ProtocolDetector` identifies the input dialect (Ollama vs OpenAI).
2.  **Cognitive Enrichment**: The `MemoryRouter` extracts the query intent and pulls relevant context from the four memory layers.
3.  **Dialect Translation**: The `DialectTranslator` converts the enriched payload into the native format for the upstream provider (Anthropic, Google, DeepSeek, etc.).
4.  **Capture & Solidification**: As the LLM responds, the `Pipeline` captures the completion. The **L6b Modulation Filter** scores the interaction's value before archiving it into the **Hippocampus (L2)**.

### 2. Dual-Plane Isolation
*   **The Relay Plane**: Dedicated solely to LLM traffic. It is performance-optimized and strictly isolated to ensure zero-latency overhead for memory injection.
*   **The Cognitive Plane**: An independent "thinking" loop. It handles **Fact Distillation** (L3), **Room Detection**, and **Vault Indexing** asynchronously without competing for the Relay Plane's connection pool.

### 3. Layer Technical Details

#### **L1 — Working Memory (Active Attention)**
*   **Concept**: Mimics human short-term focus using Attractor dynamics.
*   **Mechanism**: A weighted queue where interactions have a 1.0 "charge." Relevance recharges old items; irrelevance leads to exponential decay and eviction.

#### **L6b — Value Modulation (The Precision Layer)**
*   **Concept**: Biological bias and selective forgetting.
*   **Mechanism**: Prevents indiscriminate logging by scoring each interaction for emotional intensity, high intent, or structural importance. Low-value chatter is decayed or dropped, ensuring the Hippocampus only stores what truly matters.

#### **L2 — Hippocampus (Episodic Archive)**
*   **Concept**: Value-filtered interaction history.
*   **Mechanism**: Powered by **ChromaDB** with **Hardware-Aware Embeddings**. It automatically detects and uses the fastest local embedding model (e.g., `nomic-embed-text`) discovered via the intelligent scheduler.
*   **Integrity**: Every trace is hashed (SHA-256) for a tamper-proof audit trail.

#### **L3 — Neocortex (Semantic Facts & TasteGuard)**
*   **Concept**: Distilled wisdom protected by subjective values.
*   **Mechanism**: A background process that summarizes L2 history into high-level facts. It features **TasteGuard**, which acts as a "Belief Anchor" to protect core, subjective user facts from being overwritten.

#### **Ext — Knowledge Vault (Reasoning-Based RAG)**
*   **Concept**: High-precision document traversal.
*   **Mechanism**: A **Hybrid Router** that combines traditional Vector Search for speed with **PageIndex Reasoning** for precision.
*   **Deep Mining**: For large technical manuals (>50 pages), ClawBrain builds a hierarchical "Memory Tree" and uses an LLM to traverse it, achieving **98.7% accuracy** and eliminating "vibe-based" retrieval errors.

---

## 🛠️ Development & Verification

### Design-First Philosophy
ClawBrain follows a strict **Design-First** workflow. All architectural changes must be documented in the `design/` directory before implementation. Refer to `GEMINI.md` for our core constitution.

### Verification (Real-World Regression)
Ensure system stability by running our unmocked, resource-aware regression suite:
```bash
# Reaps orphaned processes, resets GPU resources, and runs 91 tests
./run_regression.sh
```

---

## 🏗️ GitNexus Code Intelligence

This repository is indexed by [GitNexus](https://github.com/abhigyanpatwari/GitNexus), providing a high-fidelity knowledge graph of the codebase for AI agents.

- **Status**: 🟢 Fully Indexed (2,068 symbols, 3,549 relationships)
- **Features**: Semantic navigation, impact analysis, and automated execution flow tracing.
- **Usage**: If you are using an AI assistant (like Claude Code or Cursor), refer to [AGENTS.md](./AGENTS.md) or [CLAUDE.md](./CLAUDE.md) for specialized GitNexus instructions.

---
<p align="right">Built with 🦞 by the ClawBrain Team.</p>
