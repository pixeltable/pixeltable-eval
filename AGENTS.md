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
- Fixtures must be deterministic and < 50 MB total
- Results are JSON, one file per run batch
- Hallucinated APIs list in `verifier.py` must stay current with Pixeltable releases
