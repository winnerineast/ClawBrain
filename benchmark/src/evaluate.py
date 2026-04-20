#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
Scoring logic for benchmark results.
Uses ground-truth comparison against pre-defined expected_output.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseResult:
    test_id: str
    dimension: str
    session_id: str
    expected_output: str = ""
    # Tier 1 fields
    addition_on: str = ""       # system_prompt_addition with ClawBrain ON
    addition_off: str = ""      # baseline
    chars_used: int = 0
    budget_chars: int = 0
    latency_ms: float = 0.0
    # Tier 2 fields
    response_on: str = ""       # model response text
    response_off: str = ""      # model baseline
    latency_ms_t2: float = 0.0
    # Evaluation
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    eval_type: str = "exact_match"
    error: str = ""


@dataclass
class CaseScore:
    test_id: str
    dimension: str
    # Tier 1
    recall_on: float = 0.0      # 1.0 if expected_output found in addition_on
    recall_off: float = 0.0
    isolation_pass: bool = True
    budget_efficiency: float = 0.0
    latency_ms: float = 0.0
    # Tier 2
    response_recall_on: float = 0.0  # 1.0 if expected_output matches response_on
    response_recall_off: float = 0.0
    # Delta
    delta_t1: float = 0.0
    delta_t2: float = 0.0
    error: str = ""


def _normalize(text: str) -> str:
    """Lowercase and strip non-alphanumeric noise for robust matching."""
    return re.sub(r'[^a-z0-9]', '', text.lower())


def _is_match(actual: str, expected: str) -> float:
    """
    Returns 1.0 if expected is found within actual (normalized).
    This handles cases where the model might say "The value is X"
    instead of just "X".
    """
    if not expected:
        return 1.0
    
    norm_actual = _normalize(actual)
    norm_expected = _normalize(expected)
    
    if not norm_expected:
        return 1.0
        
    return 1.0 if norm_expected in norm_actual else 0.0


def _isolation_check(text: str, forbidden: list[str]) -> bool:
    """True if none of the forbidden patterns appear in text."""
    norm_text = _normalize(text)
    for p in forbidden:
        norm_p = _normalize(p)
        if norm_p and norm_p in norm_text:
            return False
    return True


def score_case(result: CaseResult) -> CaseScore:
    s = CaseScore(test_id=result.test_id, dimension=result.dimension)
    s.error = result.error

    if result.error:
        return s

    expected = result.expected_output

    # ── Abstention logic (v1.1) ──────────────────────────────────────────────
    if result.eval_type == "abstention":
        # Tier 1 Pass: No context was injected for an unknown fact
        s.recall_on = 1.0 if not result.addition_on.strip() else 0.0
        s.recall_off = 1.0 if not result.addition_off.strip() else 0.0
        
        # Tier 2 Pass: Model correctly says "I don't know"
        if result.response_on:
            s.response_recall_on = 1.0 if any(_normalize(p) in _normalize(result.response_on) for p in result.must_contain) else 0.0
            s.response_recall_off = 1.0 if any(_normalize(p) in _normalize(result.response_off) for p in result.must_contain) else 0.0
        
        s.delta_t1 = s.recall_on - s.recall_off
        s.delta_t2 = s.response_recall_on - s.response_recall_off
        return s

    # ── Tier 1 scoring ────────────────────────────────────────────────────────
    # We check if the ground truth is present in the context addition
    s.recall_on = _is_match(result.addition_on, expected)
    s.recall_off = _is_match(result.addition_off, expected)
    s.delta_t1 = s.recall_on - s.recall_off

    # Phase 41: Targeted Isolation Check
    # Only check the HIPPOCAMPUS section for session leaks.
    # VAULT is global and permitted to appear in any session.
    hippo_match = re.search(r"=== RELEVANT HISTORICAL SNIPPETS \(HIPPOCAMPUS\) ===(.*?)\n\n", result.addition_on, re.DOTALL)
    text_to_check = hippo_match.group(1) if hippo_match else result.addition_on
    
    s.isolation_pass = _isolation_check(text_to_check, result.must_not_contain)

    if result.budget_chars > 0:
        s.budget_efficiency = result.chars_used / result.budget_chars
    s.latency_ms = result.latency_ms

    # ── Tier 2 scoring ────────────────────────────────────────────────────────
    # We check if the model's response matches the ground truth
    if result.response_on:
        s.response_recall_on = _is_match(result.response_on, expected)
        s.response_recall_off = _is_match(result.response_off, expected)
        s.delta_t2 = s.response_recall_on - s.response_recall_off

    return s


@dataclass
class DimensionSummary:
    dimension: str
    n_cases: int = 0
    recall_on_mean: float = 0.0
    recall_off_mean: float = 0.0
    delta_t1_mean: float = 0.0
    isolation_failures: int = 0
    budget_efficiency_mean: float = 0.0
    latency_p95: float = 0.0
    response_recall_on_mean: float = 0.0
    response_recall_off_mean: float = 0.0
    delta_t2_mean: float = 0.0


def summarize(scores: list[CaseScore]) -> list[DimensionSummary]:
    from collections import defaultdict
    import statistics

    by_dim: dict[str, list[CaseScore]] = defaultdict(list)
    for s in scores:
        by_dim[s.dimension].append(s)

    summaries = []
    for dim, dim_scores in sorted(by_dim.items()):
        valid = [s for s in dim_scores if not s.error]
        if not valid:
            continue
        sm = DimensionSummary(dimension=dim, n_cases=len(valid))
        sm.recall_on_mean = statistics.mean(s.recall_on for s in valid)
        sm.recall_off_mean = statistics.mean(s.recall_off for s in valid)
        sm.delta_t1_mean = statistics.mean(s.delta_t1 for s in valid)
        sm.isolation_failures = sum(1 for s in valid if not s.isolation_pass)
        
        effs = [s.budget_efficiency for s in valid if s.budget_efficiency > 0]
        sm.budget_efficiency_mean = statistics.mean(effs) if effs else 0.0

        lats = sorted(s.latency_ms for s in valid if s.latency_ms > 0)
        if lats:
            sm.latency_p95 = lats[int(len(lats) * 0.95)]

        t2 = [s for s in valid if s.response_recall_on > 0 or s.response_recall_off > 0]
        if t2:
            sm.response_recall_on_mean = statistics.mean(s.response_recall_on for s in t2)
            sm.response_recall_off_mean = statistics.mean(s.response_recall_off for s in t2)
            sm.delta_t2_mean = statistics.mean(s.delta_t2 for s in t2)

        summaries.append(sm)
    return summaries


def format_report(summaries: list[DimensionSummary], tier: int = 1) -> str:
    lines = []
    lines.append("=" * 78)
    lines.append(f"  CLAWBRAIN GROUND-TRUTH BENCHMARK REPORT — Tier {tier}")
    lines.append("=" * 78)

    if tier == 1:
        lines.append(f"\n{'Dimension':<20} {'N':>4}  {'ON':>6}  {'OFF':>6}  {'Delta':>7}  {'IsoFail':>7}")
        lines.append("-" * 60)
        for s in summaries:
            iso_warn = f"  *** {s.isolation_failures} ISOLATION FAIL ***" if s.isolation_failures else ""
            lines.append(
                f"{s.dimension:<20} {s.n_cases:>4}  "
                f"{s.recall_on_mean:>6.1%}  {s.recall_off_mean:>6.1%}  "
                f"{s.delta_t1_mean:>+7.1%}  "
                f"{s.isolation_failures:>7}"
                f"{iso_warn}"
            )
    elif tier == 2:
        lines.append(f"\n{'Dimension':<20} {'N':>4}  {'ON':>6}  {'OFF':>6}  {'Delta':>7}")
        lines.append("-" * 50)
        for s in summaries:
            lines.append(
                f"{s.dimension:<20} {s.n_cases:>4}  "
                f"{s.response_recall_on_mean:>6.1%}  {s.response_recall_off_mean:>6.1%}  "
                f"{s.delta_t2_mean:>+7.1%}"
            )

    lines.append("=" * 78)
    return "\n".join(lines)
