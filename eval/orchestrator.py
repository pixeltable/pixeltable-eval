"""
Eval orchestrator.

Runs the full matrix: stories × runners × context levels × reps.
Collects results as JSON for analysis.

Usage:
    python -m eval.orchestrator --story u1 --runner claude_code --context cold skill --reps 3
    python -m eval.orchestrator --spike  # R0 spike: U1 × claude_code × all contexts × 3 reps
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from eval.environments.setup import ContextLevel, setup_environment
from eval.runners.base import RunnerResult
from eval.runners.claude_code import ClaudeCodeRunner
from eval.runners.cursor_sdk import CursorSdkRunner
from eval.sandbox import PixeltableSandbox
from eval.stories.u1_pdf_rag import PROMPT as U1_PROMPT, U1PdfRagVerifier
from eval.verifier import VerificationResult


RUNNERS = {
    "claude_code": ClaudeCodeRunner,
    "cursor_sdk": CursorSdkRunner,
}

STORIES = {
    "u1": (U1_PROMPT, U1PdfRagVerifier),
}

FIXTURES = {
    "u1": Path(__file__).parent.parent / "fixtures" / "u1",
}

RESULTS_DIR = Path(__file__).parent.parent / "results"


def run_single_cell(
    story_id: str,
    runner_name: str,
    context: ContextLevel,
    rep: int,
) -> dict:
    """Execute one cell of the eval matrix."""

    prompt, verifier_cls = STORIES[story_id]
    runner = RUNNERS[runner_name]()
    verifier = verifier_cls()
    fixture_dir = FIXTURES.get(story_id)

    workdir = Path(tempfile.mkdtemp(prefix=f"pxteval_{story_id}_{context.value}_"))

    try:
        setup_environment(workdir, context, fixture_dir)

        print(f"  Running {runner_name} | {context.value} | rep {rep} ...")
        runner_result: RunnerResult = runner.run(prompt, workdir, timeout=300)

        if runner_result.error and not runner_result.extracted_code:
            return _make_result(
                story_id, runner_name, context, rep, runner_result,
                verification=None, error=runner_result.error,
            )

        code = runner_result.extracted_code

        with PixeltableSandbox(fixture_dir=fixture_dir) as sandbox:
            verification: VerificationResult = verifier.verify(code, sandbox)

        return _make_result(
            story_id, runner_name, context, rep, runner_result, verification,
        )

    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _make_result(
    story_id: str,
    runner_name: str,
    context: ContextLevel,
    rep: int,
    runner_result: RunnerResult,
    verification: VerificationResult | None,
    error: str | None = None,
) -> dict:
    result = {
        "story": story_id,
        "runner": runner_name,
        "context_level": context.value,
        "rep": rep,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runner_elapsed_seconds": runner_result.elapsed_seconds,
        "tokens_in": runner_result.tokens_in,
        "tokens_out": runner_result.tokens_out,
        "turns": runner_result.turns,
        "files_created": list(runner_result.files_created.keys()),
    }

    if verification:
        result.update({
            "pass": verification.passed,
            "static_pass": verification.static_pass,
            "functional_pass": verification.functional_pass,
            "idiomaticity": verification.idiomaticity,
            "hallucination_count": verification.hallucination_count,
            "hallucinations_found": verification.hallucinations_found,
            "positive_hits": verification.positive_hits,
            "negative_hits": verification.negative_hits,
            "functional_details": verification.functional_details,
        })
        if verification.sandbox_result:
            result["sandbox_exit_code"] = verification.sandbox_result.exit_code
            result["sandbox_stderr"] = verification.sandbox_result.stderr[:500]
    else:
        result.update({"pass": False, "error": error or "unknown"})

    return result


def run_spike():
    """R0 spike: U1 × claude_code × {cold, skill, skill_mcp} × 3 reps."""
    contexts = [ContextLevel.COLD, ContextLevel.WITH_SKILL, ContextLevel.WITH_MCP]
    reps = 3
    results = []

    print("=" * 60)
    print("R0 SPIKE: U1 (PDF RAG) × Claude Code × 3 contexts × 3 reps")
    print("=" * 60)

    for context in contexts:
        print(f"\n--- Context: {context.value} ---")
        for rep in range(1, reps + 1):
            result = run_single_cell("u1", "claude_code", context, rep)
            results.append(result)
            status = "PASS" if result.get("pass") else "FAIL"
            idiom = result.get("idiomaticity", 0)
            print(f"  Rep {rep}: {status} | idiomaticity={idiom:.1f} | "
                  f"hallucinations={result.get('hallucination_count', '?')}")

    save_results(results, "spike")
    print_summary(results)
    return results


def run_matrix(stories: list[str], runners: list[str], contexts: list[str], reps: int):
    """Run arbitrary subset of the eval matrix."""
    results = []
    context_levels = [ContextLevel(c) for c in contexts]

    for story_id in stories:
        for runner_name in runners:
            for context in context_levels:
                for rep in range(1, reps + 1):
                    result = run_single_cell(story_id, runner_name, context, rep)
                    results.append(result)
                    status = "PASS" if result.get("pass") else "FAIL"
                    print(f"  {story_id}/{runner_name}/{context.value}/rep{rep}: {status}")

    save_results(results, f"matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    print_summary(results)
    return results


def save_results(results: list[dict], name: str):
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{name}_{ts}.json"
    path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to {path}")


def print_summary(results: list[dict]):
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    by_context: dict[str, list[dict]] = {}
    for r in results:
        ctx = r.get("context_level", "?")
        by_context.setdefault(ctx, []).append(r)

    print(f"\n{'Context':<15} {'Pass Rate':>10} {'Idiom (avg)':>12} {'Halluc (avg)':>13}")
    print("-" * 52)

    for ctx in ["cold", "skill", "skill_mcp"]:
        runs = by_context.get(ctx, [])
        if not runs:
            continue
        pass_rate = sum(1 for r in runs if r.get("pass")) / len(runs) * 100
        avg_idiom = sum(r.get("idiomaticity", 0) for r in runs) / len(runs)
        avg_halluc = sum(r.get("hallucination_count", 0) for r in runs) / len(runs)
        print(f"{ctx:<15} {pass_rate:>9.0f}% {avg_idiom:>11.1f} {avg_halluc:>12.1f}")

    cold_pass = [r.get("pass") for r in by_context.get("cold", [])]
    skill_pass = [r.get("pass") for r in by_context.get("skill", [])]
    if cold_pass and skill_pass:
        cold_rate = sum(1 for p in cold_pass if p) / len(cold_pass) * 100
        skill_rate = sum(1 for p in skill_pass if p) / len(skill_pass) * 100
        lift = skill_rate - cold_rate
        print(f"\nLift (cold → skill): {lift:+.0f}pp")
        if lift >= 30:
            print("✓ DECISION: Premise validated. Build remaining 9 stories.")
        elif lift >= 10:
            print("⚠ DECISION: Weak lift. Re-examine SKILL.md content before expanding.")
        else:
            print("✗ DECISION: Skill thesis not supported. Investigate why.")


def main():
    parser = argparse.ArgumentParser(description="Pixeltable eval harness")
    parser.add_argument("--spike", action="store_true", help="Run R0 spike (U1 × claude_code × 3 contexts × 3 reps)")
    parser.add_argument("--story", nargs="+", choices=list(STORIES.keys()), default=["u1"])
    parser.add_argument("--runner", nargs="+", choices=list(RUNNERS.keys()), default=["claude_code"])
    parser.add_argument("--context", nargs="+", choices=["cold", "skill", "skill_mcp"], default=["cold", "skill"])
    parser.add_argument("--reps", type=int, default=3)
    args = parser.parse_args()

    if args.spike:
        run_spike()
    else:
        run_matrix(args.story, args.runner, args.context, args.reps)


if __name__ == "__main__":
    main()
