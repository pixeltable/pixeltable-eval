# Pixeltable Eval

Measures how well AI coding agents write Pixeltable code under different context levels (cold, with skill, with skill + MCP).

## Results

### U1 spike, corrected re-grade (claude-sonnet-4-5, n=10 per context)

30 cells were run with real `claude_code` (u1 PDF RAG), then re-graded
offline on the saved artifacts after fixing harness bugs that produced
false negatives: installed skill files counted as agent output, top-level
`@pxt.udf` rejected under `__main__` exec, TableModel answers never
materialized (no `pxt schema update`), check scripts calling a different
`pxt` than the harness interpreter, and missing env deps. Same generated
code, corrected grading:

| Context | Pass (score >= 3.0) | Functional pass | Hallucinations |
|---------|--------------------:|----------------:|---------------:|
| cold | 90% | 50% | 0 |
| skill | 90% | 20% | 0 |
| skill_mcp | 80% | 20% | 0 |

**No context lift on this story.** The earlier "+33pp skill lift" figure was
measured on stale graders that rewarded retired APIs and never executed
code; treat it as void.

Interpretation notes:

- **Pass is static-heavy.** A perfect static score alone (5.0 * 0.6 = 3.0)
  reaches the pass bar without executing, so the functional pass rate is the
  stricter "works end-to-end" measure.
- **Dominant real failure mode is the TableModel class-body DSL**: forward
  `NameError` (referencing `Chunks` inside its own definition),
  `Documents.view` (not a real API), `base=` given an iterator call instead
  of a table, `.data`/`.self_path` on Array-typed columns, and treating
  `QueryTemplateFunction` parameters as attributes (`search_chunks.question`).
- **Env deps the eval needs**: `pixeltable[serve]` for the FastAPIRouter
  stack (fastapi, uvicorn, `python-multipart` for `uploadfile_inputs`
  routes), `openai`, `tiktoken` (`token_limit` splitter),
  `spacy`+`en_core_web_sm` (sentence splitter), `sentence-transformers`
  (HF embeddings). Provider keys reach the sandbox via a symlinked
  `~/.pixeltable/config.toml`.
- **Infra flake ~10%**: every cell boots a fresh embedded postgres; a couple
  of `initdb` calls failed transiently under 30 back-to-back launches.
  Re-running a flake cell in isolation passes.

### Harness verification

The full pipeline was exercised end-to-end: env setup, file collection,
sandbox execution, functional checks, scoring, and `results.json` output.
The u1 reference answer now runs `ask()` for real — embeddings, similarity
search and `chat_completions` all fire inside the sandbox ("Employees
receive 20 vacation days per calendar year").

Functional checks prove the app works, not just that the schema exists:

- **u1** ingests the fixture PDFs, then runs a real `.similarity()` query —
  it only resolves when a live embedding index exists. Provider auth
  failures are recorded as env issues, not app defects.
- **u3** runs `pxt init` + `pxt schema update`, then `pxt service update`,
  discovers the serving port via `pxt service list --json`, and POSTs to
  `/analyze`. A pass requires a running service exposing the route; the
  service and its daemon are stopped afterward (each sandbox gets a private
  `PXT_PORT`).

### Testing the harness

```bash
pytest                 # all tests, incl. the ~15s live service test
pytest -m "not slow"   # static + canary only
```

- `tests/test_verifier.py` — static layer: `command_evidence` (prose earns
  no credit), every `HALLUCINATED_APIS` pattern must match a real snippet,
  known-good vs known-bad scoring, skipped-functional reweighting.
- `tests/test_canary.py` — every `evals/**/answer/` must satisfy its own
  `grader.py`; a failure means the grader drifted, not the agent.
- `tests/test_u3_functional.py` — end-to-end canary: a known-good
  TableModel app must boot and serve through the real sandbox.

Each result row records `environment` (resolved pixeltable/fastapi/spacy/
etc. versions) so scores are attributable to a dep set — pixeltable is
unbounded above. `--judge-model <name>` enables the cross-model LLM judge
(default off; without it the composite is static+functional only). The
summary's `Func` column shows how many cells ran the functional check vs
skipped it.

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
python -m eval.orchestrator --judge-model gpt-4o   # add the LLM judge layer
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
| u1 | PDF RAG pipeline (base table + chunk view + embedding + LLM); functional: fixture PDFs ingested + similarity query runs |
| u2 | Project scaffolding (pixeltable-new / pxt init + example); functional: skipped |
| u3 | REST API via TableModel + FastAPIRouter; functional: schema update + service actually boots and answers POST /analyze |

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

U1 outcome: no lift (90/90/80 at n=10) — below the 10pp floor, but the cell
size is too small to distinguish skill harm from noise. Before treating
"context adds nothing" as the answer, run a story where cold starts weaker
(u1 may be near-saturated) and consider tightening the pass bar so static
credit alone cannot carry a broken app.

## Requirements

- Python 3.10+
- `claude` CLI with `ANTHROPIC_API_KEY` for Claude Code runner
- Node.js 18+ with `CURSOR_API_KEY` for Cursor SDK runner
- `pip install -e .` pulls the functional-check deps (`pixeltable[serve]`
  for FastAPIRouter routes incl. `python-multipart`, openai, tiktoken,
  spacy + en_core_web_sm wheel, sentence-transformers);
  provider keys come from `~/.pixeltable/config.toml` or env vars
