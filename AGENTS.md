# AGENTS.md — For AI agents working in this repo

This repo is an eval harness that measures how well AI coding agents write Pixeltable code.

## Structure

- `eval/sandbox.py` — Isolated Pixeltable execution (fresh HOME per run)
- `eval/verifier.py` — Base verifier with static analysis and scoring
- `eval/stories/` — Per-story verifiers (positive/negative patterns + functional checks)
- `eval/runners/` — Agent drivers (Claude Code `--print`, Cursor SDK)
- `eval/environments/` — Context level setup (cold, skill, skill+MCP)
- `eval/orchestrator.py` — Matrix runner and result collection
- `fixtures/` — Test data (PDFs, audio, video) for stories
- `results/` — JSON output from runs (git-ignored)

## Rules

- Never hardcode API keys — use environment variables
- Every run must use a fresh PIXELTABLE_HOME (sandbox handles this)
- Verifiers check both static patterns AND functional correctness
- Fixtures must be deterministic and < 50 MB total
- Results are JSON, one file per run batch
