"""
Eval orchestrator.

Runs the full matrix: stories x runners x context levels x reps.
Collects results as JSON for analysis with proper statistical reporting.

Usage:
    python -m eval.orchestrator --spike
    python -m eval.orchestrator --story u1 --runner claude_code --context cold skill --reps 10
    python -m eval.orchestrator --model claude-sonnet-4-20250514
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.metadata
import json
import platform
import random
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from eval.environments.setup import ContextLevel, setup_environment
from eval.runners.base import RunnerResult
from eval.runners.claude_code import ClaudeCodeRunner
from eval.runners.cursor_sdk import CursorSdkRunner
from eval.sandbox import PixeltableSandbox
from eval.stats import (
    ConfidenceInterval,
    bootstrap_ci,
    classify_infra_error,
    cohens_h,
    fisher_exact_test,
    pass_at_k,
    pass_power_k,
    wilson_ci,
)
from eval.stories.u1_pdf_rag import PROMPT as U1_PROMPT, U1PdfRagVerifier
from eval.stories.u2_scaffolding import PROMPT as U2_PROMPT, U2ScaffoldingVerifier
from eval.stories.u3_service import PROMPT as U3_PROMPT, U3ServiceVerifier
from eval.verifier import VerificationResult


RUNNERS = {
    "claude_code": ClaudeCodeRunner,
    "cursor_sdk": CursorSdkRunner,
}

STORIES = {
    "u1": (U1_PROMPT, U1PdfRagVerifier),
    "u2": (U2_PROMPT, U2ScaffoldingVerifier),
    "u3": (U3_PROMPT, U3ServiceVerifier),
}

FIXTURES = {
    "u1": Path(__file__).parent.parent / "fixtures" / "u1",
}

RESULTS_DIR = Path(__file__).parent.parent / "results"

# Packages whose resolved versions materially change what the eval measures.
_ENV_PACKAGES = [
    "pixeltable",
    "fastapi",
    "uvicorn",
    "python-multipart",
    "spacy",
    "openai",
    "tiktoken",
    "sentence-transformers",
    "anthropic",
]


def collect_environment(judge_model: str | None = None) -> dict:
    """Resolved dependency versions for this run, recorded per result row so
    scores are attributable to a dep set (pixeltable is unbounded above)."""
    env = {
        "python": sys.version.split()[0],
        "platform": platform.system().lower(),
    }
    for pkg in _ENV_PACKAGES:
        try:
            env[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            pass
    if judge_model:
        env["judge_model"] = judge_model
    return env


def run_single_cell(
    story_id: str,
    runner_name: str,
    context: ContextLevel,
    rep: int,
    model: str | None = None,
    run_dir: Path | None = None,
    judge=None,
) -> dict:
    """Execute one cell of the eval matrix."""

    prompt, verifier_cls = STORIES[story_id]
    runner_kwargs = {}
    if model:
        runner_kwargs["model"] = model
    runner = RUNNERS[runner_name](**runner_kwargs)
    verifier = verifier_cls()
    fixture_dir = FIXTURES.get(story_id)

    workdir = Path(tempfile.mkdtemp(prefix=f"pxteval_{story_id}_{context.value}_"))

    try:
        setup_environment(workdir, context, fixture_dir)

        print(f"  Running {runner_name} | {context.value} | rep {rep} ...", flush=True)
        runner_result: RunnerResult = runner.run(prompt, workdir, timeout=600)

        # Save transcript and code if run_dir provided
        if run_dir:
            _save_artifacts(run_dir, context, rep, runner_result)

        if runner_result.error and not runner_result.extracted_code:
            return _make_result(
                story_id, runner_name, context, rep, runner_result,
                verification=None, error=runner_result.error,
                judge_model=getattr(judge, "model", None),
            )

        code = runner_result.extracted_code
        # All created files are evidence for static analysis. The sandbox only
        # ever executes ``code`` (the extracted entry point), so non-Python
        # files here are safe to include.
        extra_evidence = "\n\n".join(runner_result.files_created.values())

        judge_result = None
        if judge is not None:
            jr = judge.grade(code, task=prompt)
            judge_result = dataclasses.asdict(jr)

        with PixeltableSandbox(fixture_dir=fixture_dir) as sandbox:
            # Mirror the agent's files into the sandbox so multi-file projects
            # resolve imports and pxt commands find the real layout.
            for name, content in runner_result.files_created.items():
                dest = (sandbox.workdir / name).resolve()
                if not dest.is_relative_to(sandbox.workdir.resolve()):
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content)
            verification: VerificationResult = verifier.verify(
                code,
                sandbox=sandbox,
                llm_judge_result=judge_result,
                transcript=runner_result.raw_output,
                extra_evidence=extra_evidence,
            )

        return _make_result(
            story_id, runner_name, context, rep, runner_result, verification,
            judge_model=getattr(judge, "model", None),
        )

    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _save_artifacts(run_dir: Path, context: ContextLevel, rep: int, runner_result: RunnerResult):
    """Save transcript and extracted code for manual review."""
    transcripts_dir = run_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    code_dir = run_dir / "code"
    code_dir.mkdir(parents=True, exist_ok=True)

    label = f"{context.value}_rep{rep}"

    if runner_result.raw_output:
        (transcripts_dir / f"{label}.txt").write_text(runner_result.raw_output)

    if runner_result.extracted_code:
        (code_dir / f"{label}.py").write_text(runner_result.extracted_code)

    if runner_result.files_created:
        files_dir = code_dir / label
        files_dir.mkdir(exist_ok=True)
        for fname, content in runner_result.files_created.items():
            dest = (files_dir / fname).resolve()
            if not dest.is_relative_to(files_dir.resolve()):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content)


def _make_result(
    story_id: str,
    runner_name: str,
    context: ContextLevel,
    rep: int,
    runner_result: RunnerResult,
    verification: VerificationResult | None,
    error: str | None = None,
    judge_model: str | None = None,
) -> dict:
    result = {
        "story": story_id,
        "runner": runner_name,
        "context_level": context.value,
        "rep": rep,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": collect_environment(judge_model),
        "runner_elapsed_seconds": runner_result.elapsed_seconds,
        "tokens_in": runner_result.tokens_in,
        "tokens_out": runner_result.tokens_out,
        "turns": runner_result.turns,
        "files_created": list(runner_result.files_created.keys()),
    }

    err = error or runner_result.error
    is_infra = classify_infra_error(err)
    result["is_infra_error"] = is_infra

    if verification:
        result.update({
            "pass": verification.passed,
            "score": verification.score,
            "static_score": verification.static_score,
            "static_pass": verification.static_pass,
            "llm_score": verification.llm_score,
            "functional_pass": verification.functional_pass,
            "idiomaticity": verification.idiomaticity,
            "hallucination_count": verification.hallucination_count,
            "hallucinations_found": verification.hallucinations_found,
            "positive_hits": verification.positive_hits,
            "negative_hits": verification.negative_hits,
            "functional_details": verification.functional_details,
            "llm_details": verification.llm_details,
        })
        if verification.sandbox_result:
            result["sandbox_exit_code"] = verification.sandbox_result.exit_code
            result["sandbox_stderr"] = verification.sandbox_result.stderr[:500]
    else:
        result.update({"pass": False, "score": 0.0, "error": err or "unknown"})

    return result


def _make_judge(judge_model: str | None):
    """Build the optional cross-model LLM judge; None keeps the default run
    static+functional only."""
    if not judge_model:
        return None
    from eval.graders.llm_judge import LLMJudge

    return LLMJudge(model=judge_model)


def run_spike(model: str | None = None, reps: int = 10, judge_model: str | None = None):
    """R0 spike: U1 x claude_code x {cold, skill, skill_mcp} x N reps (randomized order)."""
    contexts = [ContextLevel.COLD, ContextLevel.WITH_SKILL, ContextLevel.WITH_MCP]
    results = []

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_DIR / f"spike_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60, flush=True)
    print(f"SPIKE: U1 (PDF RAG) x Claude Code x 3 contexts x {reps} reps")
    print(f"Model: {model or 'default'}")
    print("=" * 60, flush=True)

    judge = _make_judge(judge_model)

    # Randomize trial order to prevent systematic bias
    trials = [(ctx, rep) for ctx in contexts for rep in range(1, reps + 1)]
    random.shuffle(trials)

    for i, (context, rep) in enumerate(trials, 1):
        print(f"\n[{i}/{len(trials)}] ", end="", flush=True)
        result = run_single_cell("u1", "claude_code", context, rep, model=model, run_dir=run_dir, judge=judge)
        results.append(result)
        status = "PASS" if result.get("pass") else "FAIL"
        infra = " [INFRA]" if result.get("is_infra_error") else ""
        idiom = result.get("idiomaticity", 0)
        print(f"  => {status}{infra} | idiom={idiom:.1f} | "
              f"halluc={result.get('hallucination_count', '?')}", flush=True)

    save_results(results, run_dir / "results.json")
    print_summary(results)
    return results


def run_matrix(
    stories: list[str],
    runners: list[str],
    contexts: list[str],
    reps: int,
    model: str | None = None,
    judge_model: str | None = None,
):
    """Run arbitrary subset of the eval matrix with randomized trial order."""
    results = []
    context_levels = [ContextLevel(c) for c in contexts]
    judge = _make_judge(judge_model)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_DIR / f"matrix_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Build and randomize trial list
    trials = [
        (sid, rname, ctx, rep)
        for sid in stories
        for rname in runners
        for ctx in context_levels
        for rep in range(1, reps + 1)
    ]
    random.shuffle(trials)

    for i, (story_id, runner_name, context, rep) in enumerate(trials, 1):
        print(f"[{i}/{len(trials)}] ", end="", flush=True)
        result = run_single_cell(story_id, runner_name, context, rep, model=model, run_dir=run_dir, judge=judge)
        results.append(result)
        status = "PASS" if result.get("pass") else "FAIL"
        infra = " [INFRA]" if result.get("is_infra_error") else ""
        print(f"  => {status}{infra}", flush=True)

    save_results(results, run_dir / "results.json")
    print_summary(results)
    return results


def save_results(results: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to {path}", flush=True)


def print_summary(results: list[dict]):
    """Print summary with confidence intervals, pass^k, and saturation warnings."""
    print("\n" + "=" * 70, flush=True)
    print("SUMMARY (with 95% Wilson confidence intervals)")
    print("=" * 70, flush=True)

    by_context: dict[str, list[dict]] = {}
    for r in results:
        ctx = r.get("context_level", "?")
        by_context.setdefault(ctx, []).append(r)

    # Separate infra errors
    print("\n--- Infrastructure Errors (excluded from capability metrics) ---")
    total_infra = sum(1 for r in results if r.get("is_infra_error"))
    if total_infra:
        for r in results:
            if r.get("is_infra_error"):
                print(f"  {r['context_level']}/rep{r['rep']}: {r.get('error', '?')[:80]}")
        print(f"  Total: {total_infra}/{len(results)} trials affected")
    else:
        print("  None detected.")

    # Capability metrics (excluding infra errors)
    print(f"\n--- Capability Metrics (infra errors excluded) ---")
    header = f"{'Context':<12} {'Pass Rate':<22} {'Idiom':<18} {'Halluc':>8} {'Func':>7} {'n':>4}"
    print(header)
    print("-" * len(header))

    context_stats: dict[str, dict] = {}

    for ctx in ["cold", "skill", "skill_mcp", "plugin"]:
        runs = by_context.get(ctx, [])
        if not runs:
            continue

        # Exclude infra errors for capability assessment
        valid = [r for r in runs if not r.get("is_infra_error")]
        if not valid:
            print(f"{ctx:<12} {'(all infra errors)':<22}")
            continue

        n = len(valid)
        successes = sum(1 for r in valid if r.get("pass"))
        ci = wilson_ci(successes, n)

        idiom_values = [r.get("idiomaticity", 0) for r in valid if r.get("pass") is not None]
        idiom_ci = bootstrap_ci(idiom_values) if idiom_values else None

        avg_halluc = sum(r.get("hallucination_count", 0) for r in valid) / n

        # Functional coverage: how many cells actually executed the sandbox
        # check vs skipped it (e.g. pxt CLI missing). A skipped check is not a
        # failure -- it silently reweights the composite to static+LLM.
        func_ran = sum(1 for r in valid if r.get("functional_pass") is not None)
        func_str = f"{func_ran}/{n}"

        pass_str = f"{ci.point*100:.0f}% [{ci.lower*100:.0f}-{ci.upper*100:.0f}%]"
        idiom_str = f"{idiom_ci.point:.1f} [{idiom_ci.lower:.1f}-{idiom_ci.upper:.1f}]" if idiom_ci else "N/A"
        print(f"{ctx:<12} {pass_str:<22} {idiom_str:<18} {avg_halluc:>7.1f} {func_str:>7} {n:>4}")

        context_stats[ctx] = {
            "n": n,
            "successes": successes,
            "ci": ci,
            "idiom_ci": idiom_ci,
            "pass_rate": successes / n if n else 0,
        }

    print("  (Func = cells where the sandbox functional check actually ran;"
          " skipped checks reweight to static+LLM)")

    # Consistency metrics
    print(f"\n--- Consistency (pass^k) ---")
    for ctx, stats in context_stats.items():
        rate = stats["pass_rate"]
        k = stats["n"]
        pk = pass_power_k(rate, min(k, 5))
        print(f"  {ctx}: pass^{min(k,5)} = {pk:.3f} (all {min(k,5)} consecutive trials pass)")

    # Lift analysis with statistical tests
    if "cold" in context_stats and "skill" in context_stats:
        cold_s = context_stats["cold"]
        skill_s = context_stats["skill"]

        print(f"\n--- Lift Analysis (cold -> skill) ---")
        lift = (skill_s["pass_rate"] - cold_s["pass_rate"]) * 100
        print(f"  Raw lift: {lift:+.0f}pp")

        # CI overlap check
        if cold_s["ci"].overlaps(skill_s["ci"]):
            print(f"  WARNING: Confidence intervals overlap -- lift is NOT statistically significant")
            print(f"    Cold CI:  {cold_s['ci']}")
            print(f"    Skill CI: {skill_s['ci']}")
        else:
            print(f"  Confidence intervals do NOT overlap -- lift appears significant")

        # Fisher exact test
        cold_fail = cold_s["n"] - cold_s["successes"]
        skill_fail = skill_s["n"] - skill_s["successes"]
        p_val = fisher_exact_test(
            skill_s["successes"], skill_fail,
            cold_s["successes"], cold_fail,
        )
        print(f"  Fisher exact p-value: {p_val:.4f} {'(significant)' if p_val < 0.05 else '(NOT significant)'}")

        # Effect size
        h = cohens_h(skill_s["pass_rate"], cold_s["pass_rate"])
        size = "small" if abs(h) < 0.5 else "medium" if abs(h) < 0.8 else "large"
        print(f"  Cohen's h effect size: {h:.3f} ({size})")

        # Directional signal (replaces deterministic DECISION gate)
        print(f"\n--- Interpretation ---")
        if p_val < 0.05 and not cold_s["ci"].overlaps(skill_s["ci"]):
            print("  SIGNAL: Statistically significant lift detected.")
        elif lift > 0 and cold_s["pass_rate"] < 0.9:
            print("  SIGNAL: Positive directional trend, but insufficient power to confirm.")
            total_n = cold_s["n"] + skill_s["n"]
            print(f"  Recommendation: Increase reps. Current total n={total_n}.")
        elif cold_s["pass_rate"] >= 0.9:
            print("  SATURATION WARNING: Cold baseline >= 90% pass rate.")
            print("  The model likely has Pixeltable in its training data.")
            print("  Consider: (a) harder tasks, (b) different model, (c) reframe as variance-reduction measurement.")
        else:
            print("  NO SIGNAL: Cannot detect meaningful lift from this data.")

    # Saturation check
    saturated = [ctx for ctx, s in context_stats.items() if s["pass_rate"] == 1.0 and s["n"] >= 5]
    if saturated:
        print(f"\n  SATURATION: Contexts at 100%: {', '.join(saturated)}")
        print("  These provide regression signal but no room for improvement measurement.")
        print("  Add harder tasks to restore capability-eval utility.")


def main():
    parser = argparse.ArgumentParser(description="Pixeltable eval harness")
    parser.add_argument("--spike", action="store_true", help="Run spike (U1 x claude_code x 3 contexts)")
    parser.add_argument("--story", nargs="+", choices=list(STORIES.keys()), default=list(STORIES.keys()))
    parser.add_argument("--runner", nargs="+", choices=list(RUNNERS.keys()), default=["claude_code"])
    parser.add_argument("--context", nargs="+", choices=["cold", "skill", "skill_mcp", "plugin"], default=["cold", "skill"])
    parser.add_argument("--reps", type=int, default=10, help="Repetitions per cell (default: 10)")
    parser.add_argument("--model", type=str, default=None, help="Model to use (e.g., claude-sonnet-4-20250514)")
    parser.add_argument("--judge-model", type=str, default=None,
                        help="Enable the cross-model LLM judge (e.g., gpt-4o); default off")
    args = parser.parse_args()

    if args.spike:
        run_spike(model=args.model, reps=args.reps, judge_model=args.judge_model)
    else:
        run_matrix(args.story, args.runner, args.context, args.reps, model=args.model,
                   judge_model=args.judge_model)


if __name__ == "__main__":
    main()
