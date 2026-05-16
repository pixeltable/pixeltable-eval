"""
Interactive CLI for running Pixeltable evals.

Usage:
    python -m eval.cli                    # Interactive menu
    python -m eval.cli list               # List all evals
    python -m eval.cli run --spike        # R0 spike
    python -m eval.cli run -c 001-rag     # Run specific category
    python -m eval.cli run -f pdf_rag     # Filter by name
    python -m eval.cli status             # Show last run results
"""

from __future__ import annotations

import argparse
import sys

from eval.loader import load_all_evals, load_evals_by_category


def cmd_list(args):
    """List all available evals by category."""
    evals = load_all_evals()
    if not evals:
        print("No evals found in evals/ directory.")
        return

    current_cat = ""
    for e in evals:
        if e.category != current_cat:
            current_cat = e.category
            print(f"\n  {current_cat}/")
        print(f"    {e.name}")
    print(f"\n  Total: {len(evals)} evals")


def cmd_run(args):
    """Run evals."""
    if args.spike:
        from eval.orchestrator import run_spike
        run_spike(model=args.model, reps=args.reps)
        return

    from eval.orchestrator import run_matrix
    contexts = args.context or ["cold", "skill"]
    runners = args.runner or ["claude_code"]
    stories = args.story or ["u1"]

    run_matrix(stories, runners, contexts, args.reps, model=args.model)


def cmd_status(args):
    """Show results from last run."""
    import json
    from pathlib import Path

    results_dir = Path(__file__).parent.parent / "results"

    # Look for results.json inside run directories first, then top-level
    run_dirs = sorted(
        [d for d in results_dir.iterdir() if d.is_dir() and (d / "results.json").exists()],
        key=lambda p: p.stat().st_mtime,
    )
    result_files = sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)

    latest = None
    if run_dirs:
        latest = run_dirs[-1] / "results.json"
    elif result_files:
        latest = result_files[-1]

    if not latest:
        print("No results found. Run evals first.")
        return

    print(f"Latest: {latest}\n")

    data = json.loads(latest.read_text())

    from eval.stats import classify_infra_error
    for r in data:
        if "is_infra_error" not in r:
            r["is_infra_error"] = classify_infra_error(r.get("error"))

    from eval.orchestrator import print_summary
    print_summary(data)

    if args.failed:
        print("\n  --- Failed Trials ---")
        for r in data:
            if not r.get("pass") and not r.get("is_infra_error"):
                ctx = r.get("context_level", "?")
                rep = r.get("rep", "?")
                score = r.get("score", 0)
                err = r.get("error", "")[:80]
                print(f"    {ctx}/rep{rep}: score={score:.1f} {err or 'below threshold'}")


def cmd_interactive(args):
    """Interactive menu."""
    evals = load_all_evals()
    print("\n  Pixeltable Eval Harness")
    print("  " + "=" * 40)
    print(f"\n  {len(evals)} evals available\n")
    print("  Commands:")
    print("    1) Run R0 spike (U1 × Claude Code × 3 contexts × 3 reps)")
    print("    2) List all evals")
    print("    3) Show last results")
    print("    q) Quit")

    choice = input("\n  > ").strip()
    if choice == "1":
        cmd_run(argparse.Namespace(spike=True, context=None, runner=None, story=None, reps=10, model=None))
    elif choice == "2":
        cmd_list(args)
    elif choice == "3":
        cmd_status(argparse.Namespace(failed=False))
    elif choice == "q":
        return
    else:
        print(f"  Unknown: {choice}")


def main():
    parser = argparse.ArgumentParser(description="Pixeltable eval harness", prog="eval")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="List all available evals")

    run_parser = subparsers.add_parser("run", help="Run evals")
    run_parser.add_argument("--spike", action="store_true", help="R0 spike")
    run_parser.add_argument("-c", "--context", nargs="+", choices=["cold", "skill", "skill_mcp", "plugin"])
    run_parser.add_argument("-r", "--runner", nargs="+", choices=["claude_code", "cursor_sdk"])
    run_parser.add_argument("-s", "--story", nargs="+")
    run_parser.add_argument("-f", "--filter", help="Regex filter on eval names")
    run_parser.add_argument("--reps", type=int, default=10)
    run_parser.add_argument("--model", type=str, default=None, help="Model to evaluate")

    status_parser = subparsers.add_parser("status", help="Show last run results")
    status_parser.add_argument("--failed", action="store_true", help="Show only failures")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        cmd_interactive(args)


if __name__ == "__main__":
    main()
