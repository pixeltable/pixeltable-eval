# AGENTS.md — For AI agents working in this repo

This repo is an eval harness that measures how well AI coding agents write Pixeltable code.

## Structure

- `eval/sandbox.py` — Isolated Pixeltable execution (fresh HOME per run)
- `eval/verifier.py` — Base verifier with static analysis and scoring (idiomaticity, hallucinations)
- `eval/stories/` — Per-story verifiers (positive/negative patterns + functional checks)
  - `u1_pdf_rag.py` — PDF RAG pipeline
  - `u2_scaffolding.py` — Project scaffolding (pixeltable-new / pxt init + example)
  - `u3_service.py` — REST API via TableModel + FastAPIRouter + `pxt service update`
- `eval/runners/` — Agent drivers (Claude Code `--print`, Cursor SDK)
- `eval/environments/` — Context level setup (cold, skill, skill+MCP, plugin)
- `eval/orchestrator.py` — Matrix runner and result collection
- `evals/` — Convex-style eval definitions (TASK.txt + grader.py per eval)
- `tests/` — Harness self-tests: static-layer unit tests, answer/ canary,
  and a live u3 service boot; run `pytest` (`-m "not slow"` for fast only)
- `fixtures/` — Test data (PDFs, audio, video) for stories
- `results/` — JSON output from runs (git-ignored)
- `stress-test-project/` — Hand-maintained suite of 17 Pixeltable apps exercising the
  current API surface (TableModel + FastAPIRouter + `pxt service`); see its README
  for verified behaviors and platform findings

## Context Levels

| Level | What's installed | Tests |
|-------|-----------------|-------|
| `cold` | Nothing — bare workspace | Baseline agent capability |
| `skill` | `npx skills add pixeltable/pixeltable-skill` | Skill lift measurement |
| `skill_mcp` | Skill + MCP server config | Full tooling stack |
| `plugin` | Claude Code marketplace plugin | Marketplace install path |

## Rules

- Never hardcode API keys — use environment variables
- Every run must use a fresh PIXELTABLE_HOME (sandbox handles this)
- Verifiers check both static patterns AND functional correctness
- A ran-and-failed functional check vetoes `pass`; skipped checks reweight
- Fixtures must be deterministic and < 50 MB total
- Results are JSON, one file per run batch
- Hallucinated APIs list in `verifier.py` must stay current with Pixeltable releases

## Extending coverage

- Curated stories live in `eval/stories/` (u1-u5) with bespoke
  `functional_check`s; register in `STORIES` in `eval/orchestrator.py`.
  Service-booting checks share `eval/stories/_service_check.py`
  (SERVICE_CHECK_PREAMBLE) — prepend it, don't copy u3's helpers again.
- `requires_sandbox = False` on a verifier keeps it static-only and skips
  the embedded-postgres boot entirely.
- `evals/<category>/<name>/` entries run through `GenericEvalVerifier`;
  their `grader.py` may set `EXECUTE_CODE = True` to require a clean sandbox
  exec. Only enable where the task is satisfiable without provider keys, or
  provider failures get classified as infra noise either way.
- Every story/eval needs an `answer/` + `grader.py` so
  `tests/test_canary.py` keeps the grader honest.

## Loop recipe (coverage growth)

Paste into `/loop`; each iteration must produce a pytest-checkable artifact:

```
Each iteration: implement exactly ONE item, then stop.
Queue: (a) write a real grader.py for an eval whose patterns are still
defaults; (b) the next story spec — eval/stories/uN_*.py with PROMPT,
positive/negative patterns, functional_check reusing
SERVICE_CHECK_PREAMBLE, a matching evals/<cat>/<name>/answer/, and STORIES
registration.
After each item run `.venv/bin/pytest -m "not slow"`. Canary must pass;
if it fails, fix the grader or answer, never weaken the test.
```
