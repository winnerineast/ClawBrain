#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
Scoring logic for benchmark results.
Works for both Tier 1 (system_prompt_addition) and Tier 2 (model response text).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseResult:
    test_id: str
    dimension: str
    session_id: str
    # Tier 1 fields
    addition_on: str = ""       # system_prompt_addition with ClawBrain ON
    addition_off: str = ""      # system_prompt_addition with ClawBrain OFF (always "")
    chars_used: int = 0
    budget_chars: int = 0
    latency_ms: float = 0.0
    # Tier 2 fields
    response_on: str = ""       # model response text with ClawBrain ON
    response_off: str = ""      # model response text with ClawBrain OFF
    latency_ms_t2: float = 0.0
    # Evaluation
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    eval_type: str = "pattern_match"
    error: str = ""


@dataclass
class CaseScore:
    test_id: str
    dimension: str
    # Tier 1
    recall_on: float = 0.0      # fraction of must_contain found in addition_on
    recall_off: float = 0.0     # always 0.0 (no memory)
    isolation_pass: bool = True  # False if any must_not_contain found (CRITICAL)
    budget_efficiency: float = 0.0
    latency_ms: float = 0.0
    # Tier 2
    response_recall_on: float = 0.0
    response_recall_off: float = 0.0
    # Delta
    delta_t1: float = 0.0       # recall_on - recall_off (Tier 1)
    delta_t2: float = 0.0       # response_recall_on - response_recall_off (Tier 2)
    # Errors
    error: str = ""


def _pattern_recall(text: str, patterns: list[str]) -> float:
    """Fraction of patterns found in text (case-insensitive)."""
    if not patterns:
        return 1.0
    text_lower = text.lower()
    found = sum(1 for p in patterns if p.lower() in text_lower)
    return found / len(patterns)


def _isolation_check(text: str, forbidden: list[str]) -> bool:
    """True if none of the forbidden patterns appear in text."""
    text_lower = text.lower()
    return all(p.lower() not in text_lower for p in forbidden)


def score_case(result: CaseResult) -> CaseScore:
    s = CaseScore(test_id=result.test_id, dimension=result.dimension)
    s.error = result.error

    if result.error:
        return s

    # ── Tier 1 scoring ────────────────────────────────────────────────────────
    if result.addition_on or result.addition_off is not None:
        s.recall_on = _pattern_recall(result.addition_on, result.must_contain)
        s.recall_off = _pattern_recall(result.addition_off, result.must_contain)
        s.delta_t1 = s.recall_on - s.recall_off

        # Isolation: must_not_contain in addition_on is a hard failure
        s.isolation_pass = _isolation_check(result.addition_on, result.must_not_contain)

        if result.budget_chars > 0:
            s.budget_efficiency = result.chars_used / result.budget_chars

        s.latency_ms = result.latency_ms

    # ── Tier 2 scoring ────────────────────────────────────────────────────────
    if result.response_on:
        s.response_recall_on = _pattern_recall(result.response_on, result.must_contain)
        s.response_recall_off = _pattern_recall(result.response_off, result.must_contain)
        s.delta_t2 = s.response_recall_on - s.response_recall_off

    return s


@dataclass
class DimensionSummary:
    dimension: str
    n_cases: int = 0
    # Tier 1
    recall_on_mean: float = 0.0
    recall_off_mean: float = 0.0
    delta_t1_mean: float = 0.0
    isolation_failures: int = 0
    budget_efficiency_mean: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    # Tier 2
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
            sm.latency_p50 = lats[int(len(lats) * 0.5)]
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
    lines.append(f"  CLAWBRAIN BENCHMARK REPORT — Tier {tier}")
    lines.append("=" * 78)

    if tier == 1:
        lines.append(f"\n{'Dimension':<20} {'N':>4}  {'ON':>6}  {'OFF':>6}  {'Delta':>7}  "
                     f"{'IsoFail':>7}  {'Budget':>7}  {'P95ms':>7}")
        lines.append("-" * 78)
        for s in summaries:
            iso_warn = f"  *** {s.isolation_failures} ISOLATION FAIL ***" if s.isolation_failures else ""
            lines.append(
                f"{s.dimension:<20} {s.n_cases:>4}  "
                f"{s.recall_on_mean:>6.1%}  {s.recall_off_mean:>6.1%}  "
                f"{s.delta_t1_mean:>+7.1%}  "
                f"{s.isolation_failures:>7}  "
                f"{s.budget_efficiency_mean:>7.1%}  "
                f"{s.latency_p95:>7.0f}"
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
    lines.append("\nColumn guide (Tier 1):")
    lines.append("  ON      = recall rate with ClawBrain enabled")
    lines.append("  OFF     = recall rate without ClawBrain (baseline)")
    lines.append("  Delta   = ON - OFF (ClawBrain's added value)")
    lines.append("  IsoFail = cross-session leakage (must be 0)")
    lines.append("  Budget  = chars_used / budget_chars")
    lines.append("  P95ms   = 95th-percentile /internal/assemble latency")
    return "\n".join(lines)
