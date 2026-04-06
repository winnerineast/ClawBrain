# design/benchmark.md v1.0

## 1. Objective

Provide a reproducible, automated benchmark that quantifies ClawBrain's value
by comparing memory recall quality with ClawBrain ON vs OFF, across multiple
test dimensions. The benchmark also validates the end-to-end integration with
the OpenClaw CLI as a second test tier.

## 2. Two Test Tiers

### Tier 1 — Direct API (no LLM required, fast, deterministic)

Drives ClawBrain's `/internal/*` endpoints directly. Measures whether
`system_prompt_addition` contains the expected facts. No language model is
involved; results are deterministic and reproducible.

```
Test Conversation
      │
      │  POST /internal/ingest  (for each setup turn)
      ▼
ClawBrain Python server
      │
      │  POST /internal/assemble  (at recall query turn)
      ▼
system_prompt_addition
      │
      ▼
Evaluator: does addition contain must_contain patterns?
```

**ClawBrain OFF baseline**: same test case run against an empty session
(no ingest calls) — `system_prompt_addition` is always empty.

### Tier 2 — OpenClaw CLI (requires local LLM, slower, evaluates real responses)

Drives the full stack: OpenClaw CLI → ClawBrain Context Engine plugin → LLM.
Measures whether the model's response correctly reflects facts from memory.

```
Test Conversation
      │
      │  openclaw agent --local --json --profile benchmark-{on|off}
      ▼
OpenClaw (calls ingest/assemble/compact/afterTurn hooks)
      │
      ▼
LLM response text
      │
      ▼
Evaluator: does response contain must_contain patterns?
```

OpenClaw profiles:
- `benchmark-on`: `contextEngine: "clawbrain"` + plugin loaded
- `benchmark-off`: `contextEngine: "legacy"` (OpenClaw built-in, no ClawBrain)

## 3. Test Dimensions

| Dim | ID | What it tests | Groups | Avg turns |
|-----|----|---------------|--------|-----------|
| Recall distance | `recall_dist` | Fact recall after N noise turns | 60 | 100 |
| Fact type | `fact_type` | Different fact categories (technical/preference/decision/relationship) | 120 | 30 |
| Fact evolution | `fact_evol` | Updated/overridden facts return latest value | 45 | 60 |
| Session isolation | `isolation` | No cross-session leakage (must be 100%) | 40 pairs | 200 |
| Noise robustness | `noise_robust` | Recall amid high noise density | 80 | 150 |
| Multi-fact synthesis | `multi_fact` | Single query needs 2–5 historical facts | 40 | 80 |
| Neocortex distillation | `neocortex` | Recall after compact + cold session restart | 30 | 120 |
| WM decay | `wm_decay` | Evicted WM items still recoverable from L2 | 20 | 60 |

## 4. Data Format

### Fact definition (`data/facts/*.jsonl`, one record per line)

```json
{
  "fact_id": "tech_001",
  "category": "database",
  "plant_message": "Our production Postgres is at pg-primary.prod.internal:5432, db=clawdb, user=svc_app",
  "recall_queries": [
    "What is the production database host?",
    "Give me the Postgres connection string."
  ],
  "must_contain": ["pg-primary.prod.internal"],
  "must_not_contain": [],
  "update_message": null
}
```

`update_message`: if non-null, planted after an initial noise block to test fact evolution.

### Noise turn pair (`data/noise/*.jsonl`, one record per line)

```json
{
  "noise_id": "eng_001",
  "domain": "engineering",
  "user": "How do I set up pre-commit hooks in a Python project?",
  "assistant": "Install pre-commit with pip, add a .pre-commit-config.yaml, then run pre-commit install."
}
```

### Generated test case (`data/generated/*.jsonl`)

```json
{
  "test_id": "recall_dist_050_tech_db_001",
  "dimension": "recall_dist",
  "params": {"distance": 50, "fact_type": "technical", "noise_domain": "engineering"},
  "session_id": "bm-recall-dist-050-001",
  "conversation": [
    {"turn": 1, "role": "user", "content": "...", "is_fact_plant": true, "fact_id": "tech_001"},
    {"turn": 2, "role": "assistant", "content": "Got it."},
    ...
    {"turn": 51, "role": "user", "content": "What is our production DB host?",
     "is_recall_query": true, "expected_facts": ["tech_001"]}
  ],
  "evaluation": {
    "must_contain": ["pg-primary.prod.internal"],
    "must_not_contain": [],
    "type": "pattern_match"
  }
}
```

## 5. Evaluation Metrics

| Metric | Formula | Ideal |
|--------|---------|-------|
| **Recall rate** | % of `must_contain` patterns found in addition/response | 100% |
| **Isolation rate** | % of `must_not_contain` patterns absent (isolation tests only) | 100% |
| **Delta vs baseline** | ClawBrain ON recall − OFF recall | Maximise |
| **Budget efficiency** | `chars_used / budget_chars` (Tier 1 only) | 0.7–0.95 |
| **P50/P95 latency** | Per-endpoint response time (Tier 1 only) | — |
| **Distillation retention** | Recall rate after compact vs before | ≥ 0.90 |

## 6. Directory Structure

```
benchmark/
  data/
    facts/
      technical.jsonl        # ~40 technical config facts
      preferences.jsonl      # ~25 user preference facts
      decisions.jsonl        # ~25 project decision facts
      relationships.jsonl    # ~20 people/role facts
    noise/
      engineering.jsonl      # ~60 engineering discussion pairs
      general.jsonl          # ~30 general conversation pairs
    generated/               # output of generate.py (gitignored)
  src/
    generate.py              # builds test cases from fact + noise libraries
    runner_direct.py         # Tier 1 runner (direct ClawBrain API)
    runner_openclaw.py       # Tier 2 runner (OpenClaw CLI)
    evaluate.py              # scoring logic
    profiles.py              # OpenClaw profile setup helpers
  run_benchmark.py           # main entry point
  results/                   # benchmark results (gitignored)
```

## 7. CLI Interface

```bash
# Generate test cases from seed data
python benchmark/run_benchmark.py generate

# Set up OpenClaw profiles (benchmark-on / benchmark-off)
python benchmark/run_benchmark.py setup-profiles

# Tier 1 only (fast, no LLM)
python benchmark/run_benchmark.py run --tier 1

# Tier 2 only (requires openclaw + local model)
python benchmark/run_benchmark.py run --tier 2

# Specific dimension
python benchmark/run_benchmark.py run --tier 1 --dim recall_dist

# Full run
python benchmark/run_benchmark.py run --tier all

# Print last results summary
python benchmark/run_benchmark.py report
```

## 8. Output Targets

- `design/benchmark.md` (this file)
- `benchmark/data/facts/*.jsonl`
- `benchmark/data/noise/*.jsonl`
- `benchmark/src/generate.py`
- `benchmark/src/runner_direct.py`
- `benchmark/src/runner_openclaw.py`
- `benchmark/src/evaluate.py`
- `benchmark/src/profiles.py`
- `benchmark/run_benchmark.py`
