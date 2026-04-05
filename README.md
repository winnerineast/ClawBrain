# 🦞 ClawBrain: The Silicon Hippocampus for your Agentic Workflow

English | [中文版](./README_CN.md)

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

ClawBrain is the **infrastructure-layer memory engine for [OpenClaw](https://github.com/openclaw/openclaw)**. It sits between OpenClaw and its LLM backend as a transparent relay — capturing every interaction automatically, distilling it into persistent knowledge, and injecting the right context at the right time. All without touching OpenClaw's config or code.

---

## Why ClawBrain, When OpenClaw Already Has Memory?

OpenClaw ships with a thoughtful memory system: `MEMORY.md` for long-term facts, daily note files for recent context, hybrid FTS5 + vector search, and an experimental Dreaming pass that promotes daily notes to long-term storage. It is genuinely well-designed.

But there are four structural limitations that ClawBrain addresses at the infrastructure level.

### 1. Memory depends on the model deciding to write it

OpenClaw's memory is **write-on-demand**. The model must notice something is worth remembering, choose to call `memory_write`, and phrase it correctly. Under load, context pressure, or a fast-moving conversation, it skips this step. Important decisions, stated preferences, and resolved problems silently disappear.

ClawBrain captures **every interaction** at the wire level — no model decision required. Nothing is left to discretion.

### 2. `MEMORY.md` is injected on every turn — and it grows

OpenClaw injects `MEMORY.md` into the system prompt at the start of every session. This is the right design choice for OpenClaw, but it has a compounding cost: as the file grows, it consumes more tokens on every turn, increases compaction frequency, and raises API costs. OpenClaw itself warns: *"Keep MEMORY.md concise — it can grow over time and lead to unexpectedly high context usage."*

ClawBrain operates on a **greedy context budget** (L3 → L2 → L1, default 2000 chars). It injects only what is relevant to the current query — not the entire memory file. The full archive lives in SQLite and is retrieved on demand.

### 3. Semantic search requires a cloud embedding API key

OpenClaw's vector search is excellent when configured, but it requires an API key from OpenAI, Gemini, Voyage, or Mistral. Without one, only keyword FTS5 search is available. For users running fully local setups (Ollama, LM Studio), this means degraded recall.

ClawBrain's two-level FTS5 search (exact phrase → keyword AND fallback) works entirely offline. No embedding API. No cloud dependency. Local-first by design.

### 4. Dreaming is experimental and opt-in

OpenClaw's Dreaming feature — which promotes short-term daily notes to long-term `MEMORY.md` — is disabled by default, requires explicit configuration, and is labelled experimental. Most users never enable it.

ClawBrain's Neocortex distillation runs automatically in the background. Every N interactions, a background task consolidates recent traces into a persistent semantic summary — always on, no configuration required.

---

## How It Works

ClawBrain is a **zero-config transparent proxy**. Point OpenClaw's model endpoint at `http://localhost:11435`. Nothing else changes.

```
OpenClaw  →  ClawBrain (port 11435)  →  Ollama / OpenAI / Claude / Gemini
                    │
         ┌──────────┴──────────┐
         │   On every request  │
         │  1. Archive trace   │  ← captures stimulus + reaction automatically
         │  2. Search memory   │  ← FTS5 recall scoped to this session
         │  3. Inject context  │  ← greedy budget, highest-value facts first
         └─────────────────────┘
```

The model receives richer context. OpenClaw sees a normal model response. The full interaction is archived for future retrieval. Everything happens in the relay — invisible to both sides.

---

## 🚀 Quick Start (Docker)

```bash
git clone https://github.com/winnerineast/ClawBrain.git
cd ClawBrain
cp .env.example .env        # configure env vars
docker compose up -d        # start on port 11435
curl http://localhost:11435/health
```

Point any LLM client at `http://127.0.0.1:11435` — no other configuration needed:

```json
"ollama": {
  "baseUrl": "http://127.0.0.1:11435",
  "apiKey": "sk-xxx..."
}
```

---

## 🏗️ Architecture: The Neural Lifecycle

```mermaid
graph LR
    subgraph Client_Side [Input]
        OC[Agent Clients / Dev Tools]
    end

    subgraph Relay_Core [ClawBrain Neural Relay]
        direction TB
        Ingress[1. Protocol Detection & Standardization]
        Process[2. Cognitive Pipeline]
        Egress[3. Dialect Translation & Relay]

        subgraph Neural_Engine [Tri-Layer Memory System]
            WM[L1 Working Memory: Active Attention]
            HP[L2 Hippocampus: Episodic Archive]
            NC[L3 Neocortex: Semantic Facts]

            WM -- Decay & Consolidation --> NC
            WM -- Physical Solidification --> HP
            NC -- Generalized Rule Injection --> Process
            HP -- Full-text Semantic Retrieval --> Process
        end

        Ingress --> Process
        Process --> Egress
    end

    subgraph Provider_Side [Output]
        LLM[Model Providers: Local or Cloud]
    end

    OC -- "Native Request (with Key)" --> Ingress
    Egress -- "Dialect Relay (with Key)" --> LLM
    LLM -- "Stream Response" --> Egress
    Egress -- "Closed-loop Archival" --> WM
    Egress -- "Real-time Relay" --> OC
```

---

## 🧠 Tri-Layer Memory Dynamics

### L1 — Working Memory (Active Attention)
- **Implementation**: In-memory Weighted OrderedDict, **per-session isolated**
- **Attractor dynamics**: New input recharges relevant old memories (weight → 1.0); irrelevant items decay exponentially below threshold 0.3 and are evicted
- **Session isolation**: Each `x-clawbrain-session` header value gets its own independent WM instance; cross-session leakage is impossible

### L2 — Hippocampus (Episodic Archive)
- **Implementation**: SQLite FTS5 + local Blob storage, **per-session filtered**
- **Two-level search**: Exact phrase match first; keyword AND fallback if no results
- **Dynamic offloading**: Payloads > 512 KB streamed to `data/blobs/`; index keeps the anchor
- **Integrity**: SHA-256 checksum bound to every trace — tamper-proof and 100% traceable
- **Auto-cleanup**: Startup purges `timestamp=0.0` dirty records, TTL-expired traces, and orphan blob files

### L3 — Neocortex (Semantic Facts)
- **Implementation**: Async distillation engine (LLM-powered background task)
- **Trigger**: When Hippocampus accumulates `distill_threshold` traces (default 50), a background worker distills fragments into a persistent fact summary
- **Recommended formula**: `distill_threshold ≈ (ContextWindow / AvgTraceSize) × 0.8`
- **Context budget**: Greedy L3 → L2 → L1 priority; total chars capped by `CLAWBRAIN_MAX_CONTEXT_CHARS`

---

## 🔄 Protocol & Provider Support

ClawBrain's universal dialect translator handles 100% of provider API differences automatically:

| Category | Providers |
|----------|-----------|
| **Local** | Ollama, LM Studio, vLLM, SGLang |
| **Cloud** | OpenAI, DeepSeek, Anthropic (Claude), Google (Gemini), xAI (Grok), Mistral, OpenRouter |

Auto-handled quirks: role merging (Anthropic), role mapping (Gemini), non-destructive model prefix stripping, tool-call tier blocking for small models.

---

## 🔐 Session Isolation

Every request is scoped to a session via a single HTTP header:

```
x-clawbrain-session: alice
```

- Working Memory (L1), Hippocampus search (L2), and context retrieval are all strictly isolated per session
- Without the header, all traffic falls into `"default"` — a warning is logged
- Session state survives server restarts via Hippocampus hydration

---

## 🛠️ Management API

```bash
# Inspect a session's memory state
GET /v1/memory/{session_id}

# Clear a session's Neocortex summary
DELETE /v1/memory/{session_id}

# Manually trigger Neocortex distillation for a session
POST /v1/memory/{session_id}/distill

# Health check
GET /health
```

---

## ⚙️ Configuration

All runtime parameters are injected via environment variables (set in `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAWBRAIN_DB_DIR` | `/app/data` | SQLite DB and blobs directory |
| `CLAWBRAIN_MAX_CONTEXT_CHARS` | `2000` | Total context budget (chars) injected per request |
| `CLAWBRAIN_TRACE_TTL_DAYS` | `30` | Trace expiry in days (`0` = disabled) |
| `CLAWBRAIN_EXTRA_PROVIDERS` | _(empty)_ | JSON string to inject additional providers at runtime |
| `CLAWBRAIN_LOCAL_MODELS` | _(empty)_ | JSON string to whitelist additional local model IDs |

**Dynamic provider injection example:**
```bash
CLAWBRAIN_EXTRA_PROVIDERS='{"myprovider": {"base_url": "http://192.168.1.10:8080", "protocol": "openai"}}'
```

---

## 🐳 Docker Deployment

```bash
docker compose up -d          # start
docker compose logs -f        # live logs
docker compose down           # stop (data persists in ./data)
```

The `./data` directory is mounted as a volume — SQLite DB and blob files survive container restarts and upgrades.

> **Note**: ClawBrain runs with `--workers 1` by default. Working Memory is in-process; horizontal scaling requires migrating L1 to an external store (e.g., Redis).

---

## 🖥️ Local Development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn src.main:app --host 0.0.0.0 --port 11435 --reload

# Run full test suite
PYTHONPATH=. pytest tests/ --ignore=tests/test_p10_auto_trigger.py -v
```

> `test_p10_auto_trigger.py` requires a live LLM (Ollama) for distillation — skip it in CI without a local model.

---

## 🛡️ Privacy & Security

ClawBrain adheres to the **"No-Shadow Principle"**:
- **Zero-Knowledge**: API keys are never recorded, saved, or persisted — held in volatile memory for instantaneous transit only
- **Transparent Relay**: Auth info is destroyed immediately upon request completion
- **Local Storage**: All memory artifacts (Hippocampus traces, Neocortex summaries) are stored exclusively in your local `data/` directory — never uploaded to any cloud

---

## 🧪 Audit Philosophy

The project follows the **GEMINI.md** constitution: design docs updated before code, every phase produces Side-by-Side audit evidence in `results/`.

Structured log tags emitted at runtime:

| Tag | Layer |
|-----|-------|
| `[DETECTOR]` | Protocol detection |
| `[PIPELINE]` | Cognitive pipeline |
| `[MODEL_QUAL]` | Tier classification & tool-call gating |
| `[HP_STOR]` | Hippocampus archival |
| `[HP_CLEAN]` | TTL / dirty-data cleanup |
| `[CTX_BUDGET]` | L3→L2→L1 budget allocation |
| `[NC_DIST]` | Neocortex distillation |
| `[SESSION]` | Session header warnings |

---

<p align="right">Generated by Claude Sonnet 4.6 based on source v1.40 (P21)</p>
