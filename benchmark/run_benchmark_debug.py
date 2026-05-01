#!/usr/bin/env python3
# Generated from design/benchmark.md v1.1
"""
ClawBrain Benchmark — main entry point (V18 - Toggle Strategy).
"""
import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Allow importing from benchmark/ and benchmark/src/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "benchmark"))
sys.path.insert(0, str(project_root / "benchmark" / "src"))

GEN_DIR    = project_root / "benchmark" / "data" / "generated"
RESULTS_DIR = project_root / "benchmark" / "results"
RESULTS_DIR.mkdir(exist_ok=True)

@dataclass
class CaseScore:
    test_id: str
    dimension: str
    recall_on: float = 0.0
    recall_off: float = 0.0
    # Context preservation
    addition_on: str = ""
    addition_off: str = ""
    isolation_pass: bool = True
    budget_efficiency: float = 0.0
    latency_ms: float = 0.0
    response_recall_on: float = 0.0
    response_recall_off: float = 0.0
    delta_t1: float = 0.0
    delta_t2: float = 0.0
    error: str = ""

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_generated(dim: str | None = None) -> list[dict]:
    cases = []
    pattern = f"{dim}.jsonl" if dim else "*.jsonl"
    for path in sorted(GEN_DIR.glob(pattern)):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line: cases.append(json.loads(line))
        except Exception as e:
            print(f"Warning: Failed to load {path}: {e}")
    return cases

def save_results(tag: str, items: list, tier: int) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{ts}_{tag}_tier{tier}.jsonl"
    with open(path, "w") as f:
        for s in items:
            data = s if isinstance(s, dict) else asdict(s)
            f.write(json.dumps(data) + "\n")
    return path

# ── Sub-commands ──────────────────────────────────────────────────────────────

def _cleanup_env():
    import subprocess
    print("[CLEANUP] Reaping legacy server processes...", end="", flush=True)
    subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
    time.sleep(2)
    print(" Done.")

def _ensure_data():
    from generate import generate_all
    if not any(GEN_DIR.glob("*.jsonl")):
        print("[DATA] No test cases found. Generating now...")
        generate_all()

def cmd_run(args: argparse.Namespace) -> None:
    from evaluate import summarize, format_report, score_case
    import subprocess

    # _cleanup_env()
    _ensure_data()

    cases = load_generated(dim=args.dim)
    if not cases:
        print(f"No cases found for dimension: {args.dim or 'ALL'}")
        return

    max_cases = args.max or len(cases)
    cases = cases[:max_cases]
    final_scores = []

    if args.tier == "1":
        print(f"Loaded {len(cases)} cases for Tier 1 Direct Run")
        # Start server automatically for Tier 1
        # print("[SERVER] Starting background engine...", end="", flush=True)
        # server_path = project_root / "venv/bin/python3"
        # server_proc = subprocess.Popen(
        #    [str(server_path), "-m", "uvicorn", "src.main:app", "--port", "11435", "--log-level", "error"],
        #    cwd=str(project_root),
        #    stdout=subprocess.DEVNULL,
        #    stderr=subprocess.DEVNULL
        # )
        # Poll health
        # import httpx
        # ready = False
        # for _ in range(15):
        #    try:
        #        if httpx.get("http://127.0.0.1:11435/health", timeout=1.0).status_code == 200: 
        #            ready = True
        #            break
        #    except: pass
        #    time.sleep(1)
        
        # if not ready:
        #    print(" SERVER NOT READY. PLEASE START IT EXTERNALLY.")
        #    return
        
        print(" Assuming Server is Ready.")

        try:
            import runner_direct
            final_scores = runner_direct.run(cases)
        finally:
            print("[SERVER] Testing Complete.")

        path = save_results("t1_final", final_scores, tier=1)
        print(f"\nFinal Report:\n{format_report(summaries := summarize(final_scores), tier=1)}")
        print(f"\nSaved to {path}")
        return

    else:
        # Tier 2 Logic
        import runner_openclaw
        print(f"Loaded {len(cases)} cases for Tier 2 Toggle Run")
        on_responses = runner_openclaw.run_segment(cases, is_on=True)
        off_responses = runner_openclaw.run_segment(cases, is_on=False)
        # ... (rest of scoring logic)

    # Phase 47: Tier 2 Toggle Logic
    print(f"Loaded {len(cases)} cases for Tier 2 Toggle Run")
    # 1. Run ON
    on_responses = runner_openclaw.run_segment(cases, is_on=True)
    
    # 2. Run OFF
    off_responses = runner_openclaw.run_segment(cases, is_on=False)

    # 3. Score & Combine
    final_scores = []
    for c in cases:
        tid = c["test_id"]
        # Create a mock result object that evaluate.py expects
        from evaluate import CaseResult
        res = CaseResult(
            test_id=tid,
            dimension=c["dimension"],
            session_id=c["session_id"],
            expected_output=c["evaluation"]["must_contain"][0] if c["evaluation"]["must_contain"] else "",
            must_contain=c["evaluation"]["must_contain"],
            must_not_contain=c["evaluation"]["must_not_contain"],
            eval_type=c["evaluation"]["type"],
            response_on=on_responses.get(tid, ""),
            response_off=off_responses.get(tid, ""),
        )
        score = score_case(res)
        final_scores.append(score)

    path = save_results("t2_final", final_scores, tier=2)
    print(f"\nFinal Report:\n{format_report(summaries := summarize(final_scores), tier=2)}")
    print(f"\nSaved to {path}")

def cmd_setup_profiles(args: argparse.Namespace) -> None:
    print("Toggle Mode selected. No separate profiles needed.")
    print("The runner will physically modify ~/.openclaw/ during execution.")

def cmd_report(args: argparse.Namespace) -> None:
    from evaluate import summarize, format_report
    result_files = sorted(RESULTS_DIR.glob("*_tier2.jsonl"), reverse=True)
    if not result_files: return
    
    scores = []
    with open(result_files[0]) as f:
        for line in f:
            if line.strip():
                scores.append(CaseScore(**json.loads(line)))
    print(format_report(summarize(scores), tier=2))

def main() -> None:
    parser = argparse.ArgumentParser(description="ClawBrain Benchmark (Toggle Mode)")
    sub = parser.add_subparsers(dest="command")
    
    p_gen = sub.add_parser("generate")
    p_gen.add_argument("--seed", type=int, default=42)
    
    sub.add_parser("setup-profiles")
    
    p_run = sub.add_parser("run")
    p_run.add_argument("--tier", choices=["1", "2"], default="2")
    p_run.add_argument("--max", type=int, default=None)
    p_run.add_argument("--dim", type=str, default=None)
    
    sub.add_parser("report")
    
    args = parser.parse_args()
    if args.command == "run": cmd_run(args)
    elif args.command == "report": cmd_report(args)
    elif args.command == "generate":
        from generate import generate_all
        generate_all(seed=args.seed)

if __name__ == "__main__":
    main()
