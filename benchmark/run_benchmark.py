#!/usr/bin/env python3
# Generated from design/benchmark.md v1.0
"""
ClawBrain Benchmark — main entry point.

Usage:
  python benchmark/run_benchmark.py generate
  python benchmark/run_benchmark.py setup-profiles
  python benchmark/run_benchmark.py run --tier 1
  python benchmark/run_benchmark.py run --tier 2
  python benchmark/run_benchmark.py run --tier all [--dim recall_dist] [--max N]
  python benchmark/run_benchmark.py report
"""
import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Allow importing from benchmark/src/
sys.path.insert(0, str(Path(__file__).parent / "src"))

GEN_DIR    = Path(__file__).parent / "data" / "generated"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_generated(dim: str | None = None) -> list[dict]:
    """Load all generated test cases, optionally filtered by dimension."""
    cases = []
    pattern = f"{dim}.jsonl" if dim else "*.jsonl"
    for path in sorted(GEN_DIR.glob(pattern)):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    cases.append(json.loads(line))
    return cases


def save_results(tag: str, items: list, tier: int) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{ts}_{tag}_tier{tier}.jsonl"
    with open(path, "w") as f:
        for s in items:
            f.write(json.dumps(asdict(s)) + "\n")
    return path


def check_server() -> bool:
    """Quick health check on the ClawBrain server."""
    import httpx
    import os
    base = os.getenv("CLAWBRAIN_URL", "http://localhost:11435")
    try:
        resp = httpx.get(f"{base}/health", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


# ── Sub-commands ──────────────────────────────────────────────────────────────

def cmd_generate(args: argparse.Namespace) -> None:
    from generate import generate_all
    counts = generate_all(seed=args.seed)
    total = sum(counts.values())
    print(f"\nDone. {total} test cases generated in {GEN_DIR}")


def cmd_setup_profiles(args: argparse.Namespace) -> None:
    from profiles import setup_profiles
    setup_profiles()


def cmd_run(args: argparse.Namespace) -> None:
    from evaluate import summarize, format_report

    if not GEN_DIR.exists() or not any(GEN_DIR.glob("*.jsonl")):
        print("No generated test cases found. Run: python run_benchmark.py generate")
        sys.exit(1)

    cases = load_generated(dim=getattr(args, "dim", None))
    if not cases:
        print(f"No cases found for dim={getattr(args, 'dim', 'all')}")
        sys.exit(1)

    max_cases: int | None = getattr(args, "max", None)
    if max_cases:
        cases = cases[:max_cases]

    print(f"Loaded {len(cases)} test cases")
    tier = args.tier

    # ── Tier 1 ────────────────────────────────────────────────────────────────
    if tier in ("1", "all"):
        print(f"\n{'='*60}")
        print("  TIER 1 — Direct API (no LLM)")
        print(f"{'='*60}")
        print(f"DEBUG_PATH: {sys.path}")
        import runner_direct
        print(f"DEBUG_IMPORT: {runner_direct.__file__}")
        from evaluate import score_case
        import httpx
        import asyncio
        
        async def run_raw():
            results = []
            for i, c in enumerate(cases):
                print(f"DEBUG: Starting case {i+1}/{len(cases)}: {c['test_id']}")
                if c['conversation']:
                    print(f"DEBUG: Turn 1 keys: {list(c['conversation'][0].keys())}")
                    # Check last turn for recall query
                    print(f"DEBUG: Last turn keys: {list(c['conversation'][-1].keys())} | is_recall: {c['conversation'][-1].get('is_recall_query')}")
                async with httpx.AsyncClient() as client:
                    res = await runner_direct.run_case(client, c)
                print(f"INTERNAL_DEBUG: {c['test_id']} res.addition_on len: {len(res.addition_on)} | Error: '{res.error}'")
                results.append(res)
            return results

        t0 = time.monotonic()
        loop = asyncio.get_event_loop()
        raw_results = loop.run_until_complete(run_raw())
        scores_t1 = [score_case(r) for r in raw_results]
        elapsed = time.monotonic() - t0

        path = save_results("t1_raw", raw_results, tier=1)
        summaries = summarize(scores_t1)
        print(format_report(summaries, tier=1))
        print(f"\nElapsed: {elapsed:.1f}s | Results: {path}")

    # ── Tier 2 ────────────────────────────────────────────────────────────────
    if tier in ("2", "all"):
        print(f"\n{'='*60}")
        print("  TIER 2 — OpenClaw CLI (requires local LLM + server)")
        print(f"{'='*60}")

        from profiles import verify_profiles
        ok, err = verify_profiles()
        if not ok:
            print(f"ERROR: {err}")
            if tier == "2":
                sys.exit(1)
        else:
            import runner_openclaw
            # Default to a smaller subset for Tier 2 to keep runtime reasonable
            t2_max = max_cases or 30
            t2_cases = cases[:t2_max]
            print(f"Running {len(t2_cases)} cases (use --max N to change)...")

            t0 = time.monotonic()
            scores_t2 = runner_openclaw.run(t2_cases)
            elapsed = time.monotonic() - t0

            path = save_results("t2", scores_t2, tier=2)
            summaries = summarize(scores_t2)
            print(format_report(summaries, tier=2))
            print(f"\nElapsed: {elapsed:.1f}s | Results: {path}")


def cmd_report(args: argparse.Namespace) -> None:
    from evaluate import CaseScore, summarize, format_report

    result_files = sorted(RESULTS_DIR.glob("*.jsonl"), reverse=True)
    if not result_files:
        print("No results found. Run: python run_benchmark.py run --tier 1")
        return

    latest = result_files[0]
    print(f"Loading: {latest}")
    scores = []
    with open(latest) as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                s = CaseScore(**d)
                scores.append(s)

    tier = 1 if "_tier1" in latest.name else 2
    summaries = summarize(scores)
    print(format_report(summaries, tier=tier))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ClawBrain Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # generate
    p_gen = sub.add_parser("generate", help="Generate test cases from seed data")
    p_gen.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")

    # setup-profiles
    sub.add_parser("setup-profiles", help="Create OpenClaw benchmark profiles")

    # run
    p_run = sub.add_parser("run", help="Run the benchmark")
    p_run.add_argument(
        "--tier", choices=["1", "2", "all"], default="1",
        help="1=direct API, 2=OpenClaw CLI, all=both (default: 1)"
    )
    p_run.add_argument("--dim", default=None,
                       help="Filter to one dimension (e.g. recall_dist)")
    p_run.add_argument("--max", type=int, default=None,
                       help="Maximum number of test cases to run")

    # report
    sub.add_parser("report", help="Print report from last results")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "setup-profiles":
        cmd_setup_profiles(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
