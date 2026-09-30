"""Render a run's results.json into committed artifacts.

Outputs:
- RESULTS.md: full table + failure reasons
- results/chart.svg: pass-rate bar chart (no deps, renders on GitHub)
- README.md: the <!-- eval-results --> block is rewritten in place, so
  the repo front page always shows the latest headline metrics

Raw transcripts and extracted code stay gitignored (arbitrary agent
output); the JSON rows are small and re-analyzable, so they are committed
alongside the rendered summary.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

from eval.stats import classify_infra_error, wilson_ci

RESULTS_DIR = Path(__file__).parent.parent / "results"
RESULTS_MD = Path(__file__).parent.parent / "RESULTS.md"
README_MD = Path(__file__).parent.parent / "README.md"
CHART_SVG = RESULTS_DIR / "chart.svg"

README_BEGIN = "<!-- eval-results:start -->"
README_END = "<!-- eval-results:end -->"

_CTX_COLORS = {
    "cold": "#8b949e",
    "skill": "#3fb950",
    "skill_mcp": "#58a6ff",
    "plugin": "#d29922",
}


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


def _groups(results: list[dict]) -> dict[tuple[str, str], list[dict]]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in results:
        groups.setdefault((r.get("story", "?"), r.get("context_level", "?")), []).append(r)
    return groups


def _pass_stats(rows: list[dict]) -> tuple[int, int, int]:
    """(valid n, passes, func-measured n) excluding infra rows."""
    valid = [r for r in rows if not r.get("is_infra_error")]
    func_ran = sum(1 for r in valid if r.get("functional_pass") is not None)
    return len(valid), sum(1 for r in valid if r.get("pass")), func_ran


def _insights(results: list[dict]) -> list[str]:
    """Auto-computed takeaways: the lines a reader should not have to derive."""
    out: list[str] = []
    valid = [r for r in results if not r.get("is_infra_error")]
    if not valid:
        return ["No capability-measured trials (all infra errors)."]

    # The core question: does the skill beat a bare agent?
    by_ctx: dict[str, list[dict]] = {}
    for r in valid:
        by_ctx.setdefault(r.get("context_level", "?"), []).append(r)
    if "cold" in by_ctx and "skill" in by_ctx:
        c, s = by_ctx["cold"], by_ctx["skill"]
        c_rate = sum(r.get("pass") for r in c) / len(c)
        s_rate = sum(r.get("pass") for r in s) / len(s)
        ci_c = wilson_ci(sum(r.get("pass") for r in c), len(c))
        ci_s = wilson_ci(sum(r.get("pass") for r in s), len(s))
        sig = "" if ci_c.overlaps(ci_s) else " (significant)"
        out.append(
            f"**Skill lift:** cold {c_rate * 100:.0f}% -> skill {s_rate * 100:.0f}%"
            f" pass rate (n={len(c)}/{len(s)}){sig}."
        )
        # Functional-only view: code that actually ran.
        cf = [r for r in c if r.get("functional_pass") is not None]
        sf = [r for r in s if r.get("functional_pass") is not None]
        if cf and sf:
            cr = sum(r.get("functional_pass") for r in cf) / len(cf)
            sr = sum(r.get("functional_pass") for r in sf) / len(sf)
            out.append(
                f"**Functional lift:** cold {cr * 100:.0f}% -> skill {sr * 100:.0f}%"
                f" on executed cells (n={len(cf)}/{len(sf)})."
            )

    # The static-vs-runtime gap is the skill's value proposition: code that
    # pattern-matches as idiomatic but does not run.
    gap = [r for r in valid if r.get("static_pass") and r.get("functional_pass") is False]
    if gap:
        out.append(
            f"**Looks-right-but-broken:** {len(gap)} cell(s) passed static checks "
            "yet failed execution -- what a good skill should reduce."
        )

    hall = Counter(
        h for r in valid for h in r.get("hallucinations_found", [])
    )
    if hall:
        top = ", ".join(f"{name} ({n}x)" for name, n in hall.most_common(3))
        out.append(f"**Hallucinated APIs:** {top}.")

    cost = [r.get("cost_usd") for r in valid if r.get("cost_usd")]
    if cost:
        turns = [r.get("turns") for r in valid if r.get("turns")]
        med = f", median {statistics.median(turns):.0f} turns" if turns else ""
        out.append(f"**Spend:** ${sum(cost):.2f} total{med}.")

    infra = len(results) - len(valid)
    if infra:
        out.append(f"{infra} trial(s) excluded as infrastructure errors.")

    return out


def _action_items(results: list[dict]) -> list[str]:
    """Failure reasons grouped: each recurring reason is a candidate fix in
    the skill, docs, or grader."""
    reasons = Counter()
    for r in results:
        if r.get("pass") or r.get("is_infra_error"):
            continue
        reason = (
            (r.get("functional_details") or {}).get("reason")
            or (r.get("functional_details") or {}).get("error")
            or r.get("error")
            or "below pass threshold"
        )
        reasons[(r.get("story", "?"), str(reason)[:120])] += 1
    return [
        f"- `{story}`: {reason} ({n}x)"
        for (story, reason), n in reasons.most_common()
    ]


def render_chart_svg(results: list[dict]) -> str:
    """Grouped bar chart: pass rate per story, one bar per context."""
    groups = _groups(results)
    stories = sorted({s for s, _ in groups})
    ctxs = [c for c in _CTX_COLORS if any(c == k[1] for k in groups)]
    if not stories or not ctxs:
        return ""

    bw, gap_b, gap_g = 26, 6, 34
    w = 90 + len(stories) * (len(ctxs) * (bw + gap_b) + gap_g)
    h, base, top = 260, 210, 40
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        'font-family="monospace" font-size="11">',
        f'<line x1="60" y1="{base}" x2="{w - 10}" y2="{base}" stroke="#888"/>',
    ]
    for pct in (25, 50, 75, 100):
        y = base - pct * (base - top) / 100
        parts.append(
            f'<text x="30" y="{y + 4}" fill="#888">{pct}%</text>'
            f'<line x1="60" y1="{y}" x2="{w - 10}" y2="{y}" stroke="#30363d"/>'
        )

    x = 70
    for story in stories:
        for ctx in ctxs:
            rows = groups.get((story, ctx))
            if not rows:
                continue
            n, wins, _ = _pass_stats(rows)
            rate = wins / n if n else 0.0
            bh = rate * (base - top)
            color = _CTX_COLORS[ctx]
            label = "infra" if not n else f"{rate * 100:.0f}%"
            parts.append(
                f'<rect x="{x}" y="{base - bh}" width="{bw}" height="{max(bh, 1)}" '
                f'fill="{color}" rx="2"/>'
                f'<text x="{x + bw / 2}" y="{base - bh - 4}" text-anchor="middle" '
                f'fill="{color}">{label}</text>'
            )
            x += bw + gap_b
        parts.append(
            f'<text x="{x - gap_b - (len(ctxs) * (bw + gap_b)) / 2}" y="{base + 16}" '
            f'text-anchor="middle" fill="#888">{story}</text>'
        )
        x += gap_g

    lx = 70
    for ctx in ctxs:
        parts.append(
            f'<rect x="{lx}" y="8" width="10" height="10" fill="{_CTX_COLORS[ctx]}"/>'
            f'<text x="{lx + 14}" y="17" fill="#888">{ctx}</text>'
        )
        lx += 14 + len(ctx) * 7 + 24
    parts.append("</svg>")
    return "".join(parts)


def _summary_block(results: list[dict], run_id: str) -> str:
    """Compact headline block shared by RESULTS.md and the README section."""
    lines = [f"**Run:** `{run_id}` | {_env_line(results) or 'env not recorded'}", ""]
    lines += [f"- {i}" for i in _insights(results)]
    lines += ["", "![pass rates](results/chart.svg)", ""]
    lines += [
        "| Story | Context | n | Pass | Func ran | Mean score |",
        "|---|---|---|---|---|---|",
    ]
    for (story, ctx), rows in sorted(_groups(results).items()):
        n, wins, func_ran = _pass_stats(rows)
        if not n:
            lines.append(f"| {story} | {ctx} | {len(rows)} | all infra | - | - |")
            continue
        ci = wilson_ci(wins, n)
        mean = sum(r.get("score", 0) for r in rows if not r.get("is_infra_error")) / n
        pass_s = f"{ci.point * 100:.0f}% [{ci.lower * 100:.0f}-{ci.upper * 100:.0f}%]"
        infra = len(rows) - n
        n_s = f"{n} (+{infra} infra)" if infra else str(n)
        lines.append(f"| {story} | {ctx} | {n_s} | {pass_s} | {func_ran}/{n} | {mean:.1f} |")
    return "\n".join(lines)


def render_results_md(results: list[dict], run_id: str) -> str:
    lines = ["# Eval Results", "", _summary_block(results, run_id)]

    vetoed = sum(
        1 for r in results if r.get("pass") and r.get("functional_pass") is False
    )
    if vetoed:
        lines += [
            "",
            f"> **Note:** {vetoed} row(s) passed despite a failed functional "
            f"check. This run predates the functional veto; re-run before "
            f"citing these pass rates.",
        ]

    items = _action_items(results)
    if items:
        lines += [
            "",
            "## Action items",
            "",
            "Recurring failure reasons are candidates for skill, docs, or "
            "grader fixes. Investigate any reason that repeats.",
            "",
            *items,
        ]
    lines += [
        "",
        f"Raw data: `results/{run_id}/results.json`; transcripts stay local.",
    ]
    return "\n".join(lines) + "\n"


def update_readme(block: str) -> bool:
    """Rewrite the <!-- eval-results --> section of README.md in place."""
    if not README_MD.exists():
        return False
    text = README_MD.read_text()
    if README_BEGIN not in text or README_END not in text:
        return False
    head, _, rest = text.partition(README_BEGIN)
    _, _, tail = rest.partition(README_END)
    README_MD.write_text(f"{head}{README_BEGIN}\n\n{block}\n\n{README_END}{tail}")
    return True


def publish(run: Path | None = None) -> list[Path]:
    """Render a run's results.json into RESULTS.md, chart.svg, README block."""
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
    block = _summary_block(results, run_id)

    written = [RESULTS_MD]
    RESULTS_MD.write_text(render_results_md(results, run_id))

    svg = render_chart_svg(results)
    if svg:
        CHART_SVG.write_text(svg)
        written.append(CHART_SVG)

    if update_readme(block):
        written.append(README_MD)
    return written
