"""Render a run's results.json into RESULTS.md for committing to the repo.

Raw transcripts and extracted code stay gitignored (arbitrary agent
output); the JSON rows are small and re-analyzable, so they are committed
alongside the rendered summary.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.stats import classify_infra_error, wilson_ci

RESULTS_DIR = Path(__file__).parent.parent / "results"
RESULTS_MD = Path(__file__).parent.parent / "RESULTS.md"


def latest_run() -> Path | None:
    """Most recent results.json inside a run directory."""
    runs = sorted(
        (d / "results.json" for d in RESULTS_DIR.iterdir()
         if d.is_dir() and (d / "results.json").exists()),
        key=lambda p: p.stat().st_mtime,
    )
    return runs[-1] if runs else None


def _env_line(results: list[dict]) -> str:
    env = next((r.get("environment") for r in results if r.get("environment")), {})
    if not env:
        return ""
    keys = ["pixeltable", "fastapi", "openai", "python", "judge_model"]
    return ", ".join(f"{k}={env[k]}" for k in keys if k in env)


def render_results_md(results: list[dict], run_id: str) -> str:
    lines = [
        "# Eval Results",
        "",
        f"Run: `{run_id}` ({len(results)} trials)",
    ]
    env = _env_line(results)
    if env:
        lines.append(f"Environment: {env}")
    lines += [
        "",
        f"Raw data: `results/{run_id}/results.json`; transcripts stay local.",
    ]

    # Rows recorded before the functional veto can show pass=True with
    # functional_pass=False. Flag it so stale runs are not read as current.
    vetoed = sum(
        1 for r in results if r.get("pass") and r.get("functional_pass") is False
    )
    if vetoed:
        lines += [
            "",
            f"> **Note:** {vetoed} row(s) passed despite a failed functional "
            "check. This run predates the functional veto; re-run before "
            "citing these pass rates.",
        ]

    lines += [
        "",
        "| Story | Context | n | Pass | Func ran | Avg halluc | Mean score |",
        "|---|---|---|---|---|---|---|",
    ]

    groups: dict[tuple[str, str], list[dict]] = {}
    for r in results:
        groups.setdefault((r.get("story", "?"), r.get("context_level", "?")), []).append(r)

    for (story, ctx), rows in sorted(groups.items()):
        valid = [r for r in rows if not r.get("is_infra_error")]
        n = len(valid)
        infra = len(rows) - n
        if not n:
            lines.append(f"| {story} | {ctx} | {len(rows)} | all infra | - | - | - |")
            continue
        successes = sum(1 for r in valid if r.get("pass"))
        ci = wilson_ci(successes, n)
        func_ran = sum(1 for r in valid if r.get("functional_pass") is not None)
        halluc = sum(r.get("hallucination_count", 0) for r in valid) / n
        mean = sum(r.get("score", 0) for r in valid) / n
        pass_s = f"{ci.point * 100:.0f}% [{ci.lower * 100:.0f}-{ci.upper * 100:.0f}%]"
        row = f"| {story} | {ctx} | {n} | {pass_s} | {func_ran}/{n} | {halluc:.1f} | {mean:.1f} |"
        if infra:
            row = row.replace(f"| {n} |", f"| {n} (+{infra} infra) |")
        lines.append(row)

    failed = [r for r in results if not r.get("pass") and not r.get("is_infra_error")]
    if failed:
        lines += ["", "## Failures", ""]
        for r in failed:
            reason = (
                r.get("functional_details", {}).get("reason")
                or r.get("functional_details", {}).get("error")
                or r.get("error")
                or "below pass threshold"
            )
            lines.append(
                f"- `{r.get('story')}` {r.get('context_level')}/rep{r.get('rep')}: {reason}"
            )

    return "\n".join(lines) + "\n"


def publish(run: Path | None = None) -> Path:
    """Render the run's results.json to RESULTS.md. Returns the md path."""
    results_path = run or latest_run()
    if not results_path or not results_path.exists():
        raise SystemExit("no results found; run an eval first")
    results = json.loads(results_path.read_text())
    # Recompute the infra flag: marker lists improve over time and stored
    # rows were classified with whatever the list was at write time.
    for r in results:
        r["is_infra_error"] = classify_infra_error(
            r.get("error")
            or " ".join(
                str(v) for v in (r.get("functional_details") or {}).values()
            )
        )
    run_id = results_path.parent.name
    RESULTS_MD.write_text(render_results_md(results, run_id))
    return RESULTS_MD
