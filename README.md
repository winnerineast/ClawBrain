# 🦞 ClawBrain: The Silicon Hippocampus for your Agentic Workflow

English | [中文版](./README_CN.md)

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

ClawBrain is an **infrastructure-layer memory engine** designed to give AI agents (specifically [OpenClaw](https://github.com/openclaw/openclaw)) a persistent, evolving, and highly precise "brain." 

It operates as a transparent neural relay: capturing every interaction at the wire level, distilling fragments into semantic facts, and injecting exactly the right context into your model's prompt—all without you having to write a single line of code or change your agent's configuration.

---

## 📊 Cognitive Baseline (v1.1 Metrics)

ClawBrain's effectiveness is mathematically measured by its **Cognitive Delta** compared to standard stateless AI. Benchmark v1.1 integrates **ATM-Bench** concepts to measure long-term stability:

*   **Session Isolation**: **+60.0% improvement** in maintaining secure memory boundaries.
*   **Temporal Reasoning**: Successfully resolves **50.0%** of chronological fact conflicts.
*   **Recall at Distance**: **+29.2% gain** in extracting facts after 100+ turns of noise.
*   **Alias Resolution**: **33.3% success** in mapping informal nicknames to system facts.

> [!TIP]
> View the full technical breakdown in [benchmark/BASELINE.md](./benchmark/BASELINE.md).

---

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

> [!NOTE]
> **Multi-Platform Sync**: ClawBrain supports synchronized settings for macOS and Ubuntu in a single `.env` file. Use `DARWIN_` or `LINUX_` prefixes for platform-specific overrides (e.g., `LINUX_CLAWBRAIN_DB_DIR`).

---

## 🔌 Integration & Usage

ClawBrain is a universal memory hub. You can integrate it with any AI agent using three primary methods:

### Choice 1: Transparent HTTP Relay (Zero-Config)
Point your agent's API `baseUrl` to ClawBrain (port 11435). ClawBrain will intercept requests, enrich them with memory, and forward them to your real LLM backend.

**OpenClaw / OpenAI-Compatible Config:**
```json
{
  "baseUrl": "http://127.0.0.1:11435/v1",
  "apiKey": "your-key"
}
```

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

ClawBrain functions as a neural orchestrator, managing the lifecycle of information through two primary flows: **Memory Capture** and **Cognitive Optimization**.

```mermaid
flowchart LR
    %% Professional Color Palette
    classDef interface_node stroke:#27ae60,stroke-width:2px,fill:#f1f9f5,color:#1b5e20
    classDef gateway_node stroke:#e67e22,stroke-width:2px,fill:#fef5e7,color:#d35400
    classDef core_node stroke:#2980b9,stroke-width:2px,fill:#f0f7fc,color:#0d47a1
    classDef memory_node stroke:#7f8c8d,stroke-width:1px,fill:#ffffff,color:#2c3e50

    subgraph Ingress [Interfaces]
        direction TB
        API[main.py: HTTP Relay]:::interface_node
        MCP[mcp_server.py: MCP SSE]:::interface_node
        CLI[cli.py: Admin CLI]:::interface_node
    end

    subgraph Gateway [Protocol Gateway]
        direction TB
        Detector[detector.py: Detect]:::gateway_node
        Translator[translator.py: Translate]:::gateway_node
    end

    subgraph Intelligence [Core Intelligence]
        direction TB
        Pipeline[pipeline.py: Pipeline]:::core_node
        Router[router.py: Router]:::core_node
    end

    subgraph Storage [Memory Planes]
        direction TB
        L1[[working.py: L1]]:::memory_node
        L2[(storage.py: L2)]:::memory_node
        L3[neocortex.py: L3]:::memory_node
        Ext[(vault_indexer.py: Ext)]:::memory_node
    end

    Ingress --> Detector
    Detector --> Translator
    Translator --> Pipeline
    Pipeline <--> Router
    Router <--> Storage
    Pipeline <--> LLM((🤖 Upstream LLM))

    %% Professional Styling for Links
    linkStyle 0,1,2,3,4,5 stroke:#2980b9,stroke-width:3px,color:#2980b9
```

### Layer Details

#### **L1 — Working Memory (Active Attention)**
*   **The Concept**: Mimics human short-term focus.
*   **Mechanism**: A weighted queue where recent interactions have 1.0 "charge." Relevance to the current turn recharges old items, while irrelevant ones decay and are eventually evicted.
*   **Storage**: High-speed in-memory state with periodic persistence.

#### **L2 — Hippocampus (Episodic Archive)**
*   **The Concept**: Every interaction you've ever had, perfectly preserved.
*   **Mechanism**: An embedded **ChromaDB** vector store. It performs semantic search to find conversations that are conceptually similar to your current query, even if the keywords differ.
*   **Integrity**: Every trace is hashed with SHA-256 to ensure a tamper-proof historical audit trail.

#### **L3 — Neocortex (Semantic Facts)**
*   **The Concept**: Distilled wisdom.
*   **Mechanism**: A background process that periodically "reads" your L2 history and summarizes it into a single "Source of Truth" document. This provides the AI with high-level context (e.g., "The user prefers Python over Go") without wasting tokens on individual chat turns.

#### **Ext — Knowledge Vault (External Logic)**
*   **The Concept**: Bridges the gap between "what we said" and "what I know."
*   **Mechanism**: Hooks into your **Obsidian Vault**. It treats your existing notes as primary documentation, indexing them incrementally to provide the most reliable facts first.

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

- **Status**: 🟢 Fully Indexed (1,039 symbols, 2,376 relationships)
- **Features**: Semantic navigation, impact analysis, and automated execution flow tracing.
- **Usage**: If you are using an AI assistant (like Claude Code or Cursor), refer to [AGENTS.md](./AGENTS.md) or [CLAUDE.md](./CLAUDE.md) for specialized GitNexus instructions.

---
<p align="right">Built with 🦞 by the ClawBrain Team.</p>
