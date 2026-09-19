# Pixeltable Eval

Measures how well AI coding agents write Pixeltable code under different context levels (cold, with skill, with skill + MCP).

## R0 Spike Results (validated)

| Context | Pass Rate | Idiomaticity (avg) | Hallucinations (avg) |
|---------|-----------|--------------------|--------------------|
| cold | 67% | 3.0 | 0.0 |
| skill | **100%** | **5.0** | 0.0 |
| skill_mcp | **100%** | **4.8** | 0.0 |

**Lift (cold → skill): +33pp** — Premise validated.

### Harness verification (2026-09)

The full pipeline was exercised end-to-end with a fixture runner (no agent CLI):
env setup, file collection, sandbox execution, functional checks, scoring, and
`results.json` output. All three orchestrator stories pass against reference
implementations (u1: real PDF inserts, chunk view, embeddings; u3: real
`pxt init` + `pxt schema update` materializing computed columns). Functional
grading requires the harness interpreter to carry `openai` — it is now a
declared dependency. Live agent-matrix runs need `claude` CLI auth.

## Quick Start

```bash
pip install -e ".[dev]"
python scripts/generate_fixtures.py
python -m eval run --spike
```

## How It Works

```
TASK.txt → Runner (Claude Code / Cursor SDK) → Generated Code → Verifier → Score
```

**Evals** live in `evals/<category>/<name>/` (Convex-style). Each contains:
- `TASK.txt` — the prompt sent to the agent
- `answer/` — human-curated reference solution (optional)
- `grader.py` — patterns for static analysis (optional, uses defaults if missing)

**Runners** drive real agent runtimes — Claude Code via `--print` headless mode, Cursor via `@cursor/sdk`. These are NOT raw API calls; they include the full tool-use loop (file read/write, shell, web search, self-correction).

**Environments** configure context levels: cold (no hints), skill installed (`npx skills add`), skill + MCP server, plugin (Claude Code marketplace install).

**Verifiers** check static patterns (positive/negative grep) and optionally run code in a sandbox for functional correctness.

## Eval Categories

```
evals/
├── 000-fundamentals/   # create_table, computed_columns, embedding_index
├── 001-rag/            # pdf_rag, semantic_search
├── 002-video/          # frame_extraction
├── 003-agents/         # tool_calling
├── 004-idioms/         # no_langchain, no_pandas_store, computed_not_loop
├── 005-hard/           # error_recovery, incremental_update, multi_view_pipeline
├── 006-negative-controls/  # raw_sql_query, simple_pandas_groupby, static_file_transform
└── 007-scaffolding/    # use_scaffolder, pxt_service
```

## CLI

```bash
python -m eval list                    # List all evals
python -m eval run --spike             # R0 spike
python -m eval run -c skill -r claude_code --reps 3
python -m eval status                  # Show last results
python -m eval status --failed         # Show failures only
```

## Matrix

| Axis | Values |
|------|--------|
| Eval | 15+ evals across 8 categories |
| Runner | Claude Code (`--print`), Cursor SDK |
| Context | cold, +skill, +skill+MCP, +plugin |
| Reps | 3 per cell (for variance) |

## Stories (Orchestrator)

| Story | Description |
|-------|-------------|
| u1 | PDF RAG pipeline (base table + chunk view + embedding + LLM) |
| u2 | Project scaffolding (pixeltable-new / pxt init + example) |
| u3 | REST API via TableModel + FastAPIRouter (pxt schema update + pxt service update) |

## Scoring

| Metric | Range | What it measures |
|--------|-------|-----------------|
| Pass | 0/1 | All positive patterns present, no anti-patterns |
| Idiomaticity | 0-5 | Uses computed columns, embedding indexes, TableModel + FastAPIRouter, pxt service update |
| Hallucinations | int | Non-existent APIs called (lower = better) |
| Turns | int | How many agent turns to produce code |

## Decision Gate (R0 Spike)

After running the spike:
- **Lift cold → skill ≥ 30pp**: Premise validated → build remaining 9 stories ✓
- **Lift 10-30pp**: Weak → re-examine SKILL.md content
- **Lift < 10pp**: Thesis not supported → investigate
- **Variance > 25pp**: Need more reps

## Requirements

- Python 3.10+
- `claude` CLI with `ANTHROPIC_API_KEY` for Claude Code runner
- Node.js 18+ with `CURSOR_API_KEY` for Cursor SDK runner
- `pixeltable` installed for sandbox verification
