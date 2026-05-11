# Pixeltable Eval

Measures how well AI coding agents write Pixeltable code under different context levels (cold, with skill, with skill + MCP).

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Generate PDF fixtures
python scripts/generate_fixtures.py

# Run the R0 spike (U1: PDF RAG × Claude Code × 3 contexts × 3 reps)
python -m eval.orchestrator --spike
```

## How It Works

```
Prompt → Runner (Claude Code / Cursor SDK) → Generated Code → Sandbox → Verifier → Score
```

**Runners** drive real agent runtimes — Claude Code via `--print` headless mode, Cursor via `@cursor/sdk`. These are NOT raw API calls; they include the full tool-use loop (file read/write, shell, web search, self-correction).

**Environments** configure context levels: cold (no hints), skill installed (`npx skills add`), skill + MCP server.

**Sandbox** creates a fresh `PIXELTABLE_HOME` per run so state never leaks.

**Verifiers** check static patterns (positive/negative grep), run the code, and verify functional correctness.

## Matrix

| Axis | Values |
|------|--------|
| Story | U1 (PDF RAG) — more coming after R0 validates |
| Runner | Claude Code (`--print`), Cursor SDK |
| Context | cold, +skill, +skill+MCP |
| Reps | 3 per cell (for variance) |

## Custom Runs

```bash
# Single story, single runner, specific contexts
python -m eval.orchestrator --story u1 --runner claude_code --context cold skill --reps 3

# Add Cursor SDK
python -m eval.orchestrator --story u1 --runner cursor_sdk --context skill --reps 3
```

## Scoring

| Metric | Range | What it measures |
|--------|-------|-----------------|
| Pass@1 | 0/1 | Code runs AND produces correct results |
| Idiomaticity | 0-5 | Uses computed columns, embedding indexes, proper imports |
| Hallucinations | int | Non-existent APIs called (lower = better) |
| Turns | int | How many agent turns to produce code |

## Decision Gate (R0 Spike)

After running the spike:
- **Lift cold → skill ≥ 30pp**: Premise validated → build remaining 9 stories
- **Lift 10-30pp**: Weak → re-examine SKILL.md content
- **Lift < 10pp**: Thesis not supported → investigate
- **Variance > 25pp**: Need more reps

## Requirements

- Python 3.10+
- `claude` CLI with `ANTHROPIC_API_KEY` for Claude Code runner
- Node.js 18+ with `CURSOR_API_KEY` for Cursor SDK runner
- `pixeltable` installed for sandbox verification
