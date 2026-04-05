# 🦞 ClawBrain: The Silicon Hippocampus for your Agentic Workflow

English | [中文版](./README_CN.md)

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

ClawBrain is a biomimetically designed **Transparent Neural Relay Gateway**. It goes beyond multi-protocol routing by simulating the evolutionary logic of human memory, giving every LLM an "External Brain" with tri-layer memory synergy. In VRAM-constrained environments, ClawBrain significantly boosts agentic context efficiency and logical consistency.

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
