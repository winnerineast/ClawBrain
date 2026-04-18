#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
Generate structured test cases from fact and noise seed libraries.

Each test case is a conversation with:
  - fact "plant" turns (establishes information)
  - noise turns (unrelated filler, simulates real conversation)
  - recall query turns (tests whether the fact can be retrieved)

Output: benchmark/data/generated/*.jsonl
"""
import json
import random
import itertools
from pathlib import Path
from typing import Any

BENCHMARK_DIR = Path(__file__).parent.parent
DATA_DIR = BENCHMARK_DIR / "data"
GEN_DIR = DATA_DIR / "generated"
GEN_DIR.mkdir(exist_ok=True)

FACTS_DIR = DATA_DIR / "facts"
NOISE_DIR = DATA_DIR / "noise"

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def load_all_facts() -> list[dict]:
    facts = []
    for f in FACTS_DIR.glob("*.jsonl"):
        facts.extend(load_jsonl(f))
    return facts

def load_all_noise() -> list[dict]:
    noise = []
    for f in NOISE_DIR.glob("*.jsonl"):
        noise.extend(load_jsonl(f))
    return noise

# ── Conversation builders ─────────────────────────────────────────────────────

def make_noise_block(noise_pool: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Pick n noise pairs, interleaved as user/assistant turns."""
    selected = rng.sample(noise_pool, min(n, len(noise_pool)))
    turns = []
    for item in selected:
        turns.append({"role": "user", "content": item["user"]})
        turns.append({"role": "assistant", "content": item["assistant"]})
    return turns

def build_conversation(turns: list[dict]) -> list[dict]:
    """Add sequential turn numbers."""
    return [{"turn": i + 1, **t} for i, t in enumerate(turns)]

# ── Dimension generators ──────────────────────────────────────────────────────

def gen_recall_distance(
    facts: list[dict],
    noise_pool: list[dict],
    distances: list[int],
    per_distance: int,
    rng: random.Random,
) -> list[dict]:
    """Test recall at varying distances (number of noise turns between plant and query)."""
    cases = []
    fact_cycle = itertools.cycle(facts)

    for dist in distances:
        for i in range(per_distance):
            fact = next(fact_cycle)
            query_obj = rng.choice(fact["recall_queries"])
            query = query_obj["query"]
            expected = query_obj["expected_output"]

            raw_turns: list[dict] = []
            raw_turns.append({
                "role": "user",
                "content": fact["plant_message"],
                "is_fact_plant": True,
                "fact_id": fact["fact_id"],
            })
            raw_turns.append({"role": "assistant", "content": "Noted."})

            # Pad with noise turns (each noise pair = 2 turns, so dist//2 pairs)
            noise_pairs = max(1, dist // 2)
            raw_turns.extend(make_noise_block(noise_pool, noise_pairs, rng))

            raw_turns.append({
                "role": "user",
                "content": query,
                "is_recall_query": True,
                "expected_facts": [fact["fact_id"]],
            })

            test_id = f"recall_dist_{dist:03d}_{fact['fact_id']}_{i:02d}"
            cases.append({
                "test_id": test_id,
                "dimension": "recall_dist",
                "params": {"distance": dist, "fact_id": fact["fact_id"]},
                "session_id": f"bm-{test_id}",
                "conversation": build_conversation(raw_turns),
                "evaluation": {
                    "expected_output": expected,
                    "must_contain": [expected] + fact["must_contain"],
                    "must_not_contain": fact["must_not_contain"],
                    "type": "pattern_match",
                },
            })
    return cases


def gen_fact_evolution(
    facts: list[dict],
    noise_pool: list[dict],
    per_case: int,
    rng: random.Random,
) -> list[dict]:
    """Test that updated facts override stale ones."""
    updatable = [f for f in facts if f.get("update_message")]
    cases = []

    for i, fact in enumerate(updatable[:per_case]):
        query_obj = rng.choice(fact["recall_queries"])
        query = query_obj["query"]
        expected = fact.get("expected_update_output", "updated")

        raw_turns: list[dict] = []

        # Plant original fact
        raw_turns.append({
            "role": "user",
            "content": fact["plant_message"],
            "is_fact_plant": True,
            "fact_id": fact["fact_id"],
            "version": "v1",
        })
        raw_turns.append({"role": "assistant", "content": "Understood."})

        # Noise block (Increased to 20 pairs for stress testing)
        raw_turns.extend(make_noise_block(noise_pool, 20, rng))

        # Plant update
        raw_turns.append({
            "role": "user",
            "content": fact["update_message"],
            "is_fact_plant": True,
            "fact_id": fact["fact_id"],
            "version": "v2",
        })
        raw_turns.append({"role": "assistant", "content": "Got it, updated."})

        # More noise (Increased to 15 pairs)
        raw_turns.extend(make_noise_block(noise_pool, 15, rng))

        # Recall query — should return update_message content
        raw_turns.append({
            "role": "user",
            "content": query,
            "is_recall_query": True,
            "expected_facts": [fact["fact_id"]],
        })

        test_id = f"fact_evol_{fact['fact_id']}_{i:02d}"
        cases.append({
            "test_id": test_id,
            "dimension": "fact_evol",
            "params": {"fact_id": fact["fact_id"]},
            "session_id": f"bm-{test_id}",
            "conversation": build_conversation(raw_turns),
            "evaluation": {
                "expected_output": expected,
                "must_contain": [expected],
                "must_not_contain": [query_obj["expected_output"]], # Original value should NOT be there
                "type": "pattern_match",
                "note": f"Should reflect updated value: {expected}",
            },
        })
    return cases


def gen_session_isolation(
    facts: list[dict],
    noise_pool: list[dict],
    num_pairs: int,
    rng: random.Random,
) -> list[dict]:
    """
    Two sessions each plant different facts.
    Query session B must NOT return session A's facts.
    """
    cases = []
    shuffled_facts = facts.copy()
    rng.shuffle(shuffled_facts)
    fact_pairs = list(zip(shuffled_facts[::2], shuffled_facts[1::2]))[:num_pairs]

    for i, (fact_a, fact_b) in enumerate(fact_pairs):
        query_obj_b = rng.choice(fact_b["recall_queries"])
        query_b = query_obj_b["query"]
        expected_b = query_obj_b["expected_output"]
        
        expected_a = rng.choice(fact_a["recall_queries"])["expected_output"]

        # Session A conversation
        session_a = f"bm-iso-{i:02d}-a"
        raw_a: list[dict] = []
        raw_a.append({
            "role": "user",
            "content": fact_a["plant_message"],
            "is_fact_plant": True,
            "fact_id": fact_a["fact_id"],
            "session_id": session_a,
        })
        raw_a.append({"role": "assistant", "content": "Recorded."})
        raw_a.extend(make_noise_block(noise_pool, 15, rng))

        # Session B conversation
        session_b = f"bm-iso-{i:02d}-b"
        raw_b: list[dict] = []
        raw_b.append({
            "role": "user",
            "content": fact_b["plant_message"],
            "is_fact_plant": True,
            "fact_id": fact_b["fact_id"],
            "session_id": session_b,
        })
        raw_b.append({"role": "assistant", "content": "Got it."})
        raw_b.extend(make_noise_block(noise_pool, 15, rng))
        raw_b.append({
            "role": "user",
            "content": query_b,
            "is_recall_query": True,
            "expected_facts": [fact_b["fact_id"]],
        })

        test_id = f"isolation_{i:02d}"
        cases.append({
            "test_id": test_id,
            "dimension": "isolation",
            "params": {
                "session_a": session_a,
                "session_b": session_b,
                "fact_a_id": fact_a["fact_id"],
                "fact_b_id": fact_b["fact_id"],
            },
            "session_id": session_b,   # query session
            "session_id_setup": session_a,   # must be ingested first
            "conversation_setup": build_conversation(raw_a),   # ingested into session_a
            "conversation": build_conversation(raw_b),          # ingested + queried in session_b
            "evaluation": {
                "expected_output": expected_b,
                "must_contain": [expected_b],
                # Session A's facts must NEVER appear in session B's addition
                "must_not_contain": [expected_a] + fact_a["must_contain"],
                "type": "isolation",
                "note": "Cross-session leakage test — must_not_contain is a hard failure",
            },
        })
    return cases


def gen_noise_robustness(
    facts: list[dict],
    noise_pool: list[dict],
    noise_sizes: list[int],
    per_size: int,
    rng: random.Random,
) -> list[dict]:
    """Needle-in-a-haystack: one fact buried in N noise turns."""
    cases = []
    fact_cycle = itertools.cycle(facts)

    for noise_n in noise_sizes:
        for i in range(per_size):
            fact = next(fact_cycle)
            query_obj = rng.choice(fact["recall_queries"])
            query = query_obj["query"]
            expected = query_obj["expected_output"]

            raw_turns: list[dict] = []

            # Fact planted early
            raw_turns.append({
                "role": "user",
                "content": fact["plant_message"],
                "is_fact_plant": True,
                "fact_id": fact["fact_id"],
            })
            raw_turns.append({"role": "assistant", "content": "Understood."})

            # Heavy noise
            raw_turns.extend(make_noise_block(noise_pool, noise_n // 2, rng))

            raw_turns.append({
                "role": "user",
                "content": query,
                "is_recall_query": True,
                "expected_facts": [fact["fact_id"]],
            })

            test_id = f"noise_robust_{noise_n:03d}_{fact['fact_id']}_{i:02d}"
            cases.append({
                "test_id": test_id,
                "dimension": "noise_robust",
                "params": {"noise_turns": noise_n, "fact_id": fact["fact_id"]},
                "session_id": f"bm-{test_id}",
                "conversation": build_conversation(raw_turns),
                "evaluation": {
                    "expected_output": expected,
                    "must_contain": [expected],
                    "must_not_contain": fact["must_not_contain"],
                    "type": "pattern_match",
                },
            })
    return cases


def gen_multi_fact(
    facts: list[dict],
    noise_pool: list[dict],
    combo_sizes: list[int],
    per_size: int,
    rng: random.Random,
) -> list[dict]:
    """Multiple facts from the same category must all be recalled together."""
    # Group facts by category
    by_category: dict[str, list[dict]] = {}
    for f in facts:
        by_category.setdefault(f["category"], []).append(f)

    cases = []
    for combo_size in combo_sizes:
        eligible_categories = [c for c, fs in by_category.items() if len(fs) >= combo_size]
        for i in range(per_size):
            if not eligible_categories:
                continue
            cat = rng.choice(eligible_categories)
            selected_facts = rng.sample(by_category[cat], combo_size)

            raw_turns: list[dict] = []
            for j, fact in enumerate(selected_facts):
                raw_turns.append({
                    "role": "user",
                    "content": fact["plant_message"],
                    "is_fact_plant": True,
                    "fact_id": fact["fact_id"],
                })
                raw_turns.append({"role": "assistant", "content": "Noted."})
                if j < combo_size - 1:
                    raw_turns.extend(make_noise_block(noise_pool, 3, rng))

            raw_turns.extend(make_noise_block(noise_pool, 5, rng))

            # Synthesized query asking for all facts from the category
            combined_query = (
                f"List all the {cat.replace('_', ' ')} configuration values "
                "one by one. Reply concisely with only the list of values."
            )
            raw_turns.append({
                "role": "user",
                "content": combined_query,
                "is_recall_query": True,
                "expected_facts": [f["fact_id"] for f in selected_facts],
            })

            # All must_contain patterns from all selected facts
            all_expected = [rng.choice(f["recall_queries"])["expected_output"] for f in selected_facts]

            test_id = f"multi_fact_{combo_size}_{cat}_{i:02d}"
            cases.append({
                "test_id": test_id,
                "dimension": "multi_fact",
                "params": {
                    "combo_size": combo_size,
                    "category": cat,
                    "fact_ids": [f["fact_id"] for f in selected_facts],
                },
                "session_id": f"bm-{test_id}",
                "conversation": build_conversation(raw_turns),
                "evaluation": {
                    "expected_output": ", ".join(all_expected),
                    "must_contain": all_expected,
                    "must_not_contain": [],
                    "type": "pattern_match",
                },
            })
    return cases


def gen_neocortex(
    facts: list[dict],
    noise_pool: list[dict],
    per_case: int,
    rng: random.Random,
) -> list[dict]:
    """
    Plant many facts (>distill_threshold), trigger compact, then
    open a fresh sub-session and query — tests Neocortex retention.
    """
    cases = []
    for i in range(per_case):
        selected_facts = rng.sample(facts, min(12, len(facts)))
        raw_turns: list[dict] = []

        for fact in selected_facts:
            raw_turns.append({
                "role": "user",
                "content": fact["plant_message"],
                "is_fact_plant": True,
                "fact_id": fact["fact_id"],
            })
            raw_turns.append({"role": "assistant", "content": "Got it."})
            raw_turns.extend(make_noise_block(noise_pool, 2, rng))

        # Pick one fact to query after compaction
        probe_fact = rng.choice(selected_facts)
        query_obj = rng.choice(probe_fact["recall_queries"])
        probe_query = query_obj["query"]
        expected = query_obj["expected_output"]

        raw_turns.append({
            "role": "user",
            "content": probe_query,
            "is_recall_query": True,
            "expected_facts": [probe_fact["fact_id"]],
        })

        test_id = f"neocortex_{i:02d}"
        cases.append({
            "test_id": test_id,
            "dimension": "neocortex",
            "params": {
                "fact_count": len(selected_facts),
                "probe_fact_id": probe_fact["fact_id"],
                "trigger_compact": True,
            },
            "session_id": f"bm-{test_id}",
            "conversation": build_conversation(raw_turns),
            "evaluation": {
                "expected_output": expected,
                "must_contain": [expected],
                "must_not_contain": probe_fact["must_not_contain"],
                "type": "pattern_match",
                "note": "Runner must call /internal/compact before /internal/assemble",
            },
        })
    return cases


# ── Entry point ───────────────────────────────────────────────────────────────

def generate_all(seed: int = 42) -> dict[str, int]:
    rng = random.Random(seed)
    facts = load_all_facts()
    noise = load_all_noise()
    print(f"Loaded {len(facts)} facts, {len(noise)} noise pairs")

    counts: dict[str, int] = {}

    def write(dimension: str, cases: list[dict]) -> None:
        path = GEN_DIR / f"{dimension}.jsonl"
        with open(path, "w") as f:
            for c in cases:
                f.write(json.dumps(c) + "\n")
        counts[dimension] = len(cases)
        print(f"  {dimension}: {len(cases)} cases → {path}")

    print("\nGenerating test cases...")

    write("recall_dist", gen_recall_distance(
        facts, noise,
        distances=[10, 50, 100, 200, 300, 500],
        per_distance=8,
        rng=rng,
    ))

    write("fact_evol", gen_fact_evolution(
        facts, noise, per_case=20, rng=rng,
    ))

    write("isolation", gen_session_isolation(
        facts, noise, num_pairs=20, rng=rng,
    ))

    write("noise_robust", gen_noise_robustness(
        facts, noise,
        noise_sizes=[50, 100, 200, 400],
        per_size=6,
        rng=rng,
    ))

    write("multi_fact", gen_multi_fact(
        facts, noise,
        combo_sizes=[2, 3, 4],
        per_size=8,
        rng=rng,
    ))

    write("neocortex", gen_neocortex(
        facts, noise, per_case=15, rng=rng,
    ))

    total = sum(counts.values())
    print(f"\nTotal: {total} test cases across {len(counts)} dimensions")
    return counts


if __name__ == "__main__":
    generate_all()
