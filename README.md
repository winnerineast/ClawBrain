# 🦞 ClawBrain: The Silicon Hippocampus for your Agentic Workflow

English | [中文版](./README_CN.md)

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

ClawBrain is an **infrastructure-layer memory engine** designed to give AI agents (specifically [OpenClaw](https://github.com/openclaw/openclaw)) a persistent, evolving, and highly precise "brain." 

It operates as a transparent neural relay: capturing every interaction at the wire level, distilling fragments into semantic facts, and injecting exactly the right context into your model's prompt—all without you having to write a single line of code or change your agent's configuration.

---

## 💎 The ClawBrain Edge: Why use it?

Most AI memory systems are either too shallow (manual "save" tools) or too heavy (injecting massive files). ClawBrain solves this at the network layer.

### 1. 100% Passive Capture (Infrastructure vs. Model)
Traditional memory requires the model to *decide* to remember something. Under high cognitive load, models often forget to save important details. ClawBrain is **passive**: it captures 100% of interactions as they pass through the relay. Nothing is ever lost.

### 2. Semantic Recall (Local Vector Search)
While others rely on keyword matching, ClawBrain uses an **embedded ChromaDB engine**. It understands intent. Querying for "database" will find notes about "Postgres" or "data store" even if the keywords don't match.

### 3. Precision Budgeting (Stack Math)
ClawBrain doesn't just dump memory into your prompt. It uses **Greedy Context Budgeting** and **Stack Math** to calculate the exact character cost of every memory layer, ensuring your context window is used efficiently without ever overflowing.

### 4. External Knowledge Integration (Vault)
Your project isn't just in the chat history. ClawBrain can "mount" your **Obsidian Vault**, performing high-performance incremental scanning (mtime + hash) to bring your existing documentation directly into the agent's reasoning loop.

### 5. Non-Blocking Robustness
Using **Network Plane Isolation**, ClawBrain separates high-priority chat traffic from background "cognitive" tasks (like distillation or vault scanning). Your agent stays 100% responsive, even while its brain is working overtime in the background.

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

## 🔌 Integration & Usage

### Choice 1: Transparent HTTP Relay (Recommended)
Point your agent's API `baseUrl` to ClawBrain (port 11435). ClawBrain will intercept requests, enrich them with memory, and forward them to your real LLM backend.

**Example OpenClaw Provider Config:**
```json
"ollama": {
  "baseUrl": "http://127.0.0.1:11435",
  "apiKey": "optional"
}
```

### Choice 2: Native OpenClaw Plugin
ClawBrain can also run as a native Context Engine plugin.
```bash
openclaw plugins install -l ./packages/openclaw
```

### 🔐 Session Isolation
Isolate memory between different projects or users by sending a simple header:
`x-clawbrain-session: project-alpha`

---

## 🧠 Tri-Layer Memory Architecture

| Layer | Component | Function |
|---|---|---|
| **L1** | **Working Memory** | Active attention. Holds the last few turns with exponential decay. |
| **L2** | **Hippocampus** | Episodic archive. ChromaDB-powered semantic vector search. |
| **L3** | **Neocortex** | Semantic facts. Asynchronous LLM distillation of old memories into hard facts. |
| **Ext** | **Vault** | External knowledge. Incremental indexing of local Obsidian markdown notes. |

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
<p align="right">Built with 🦞 by the ClawBrain Team.</p>
