"""
U5: Incremental computation semantics

Prompt pattern adapted from evals/005-hard/incremental_update: new rows
trigger computation only on new rows; a column added after data exists
backfills all existing rows.

Verifier checks:
- Static: pixeltable table, computed columns (UDF + LLM), a second insert
  wave, a column added after data exists, no drop/recreate anti-patterns
- Negative: recreating the table or re-inserting to force recomputation,
  imperative loops calling models
- Functional: the articles table holds all inserted rows, the UDF column is
  populated on every row, and the late-added column is populated on ALL
  rows (the backfill proof). Provider-key-dependent columns are checked
  for existence, not values, so the check is hermetic.
"""

from __future__ import annotations

import json

from eval.sandbox import PixeltableSandbox
from eval.verifier import StoryVerifier

PROMPT = (
    "Build a Pixeltable pipeline that demonstrates incremental computation.\n\n"
    "Requirements:\n"
    "- Create table 'analytics/articles' with columns title (pxt.String), "
    "body (pxt.String), source (pxt.String)\n"
    "- Add computed columns: word_count (a @pxt.udf counting words), "
    "sentiment (OpenAI chat_completions classifying positive/negative/neutral), "
    "keywords (chat_completions extracting 5 keywords)\n"
    "- Insert 3 initial articles\n"
    "- Insert 2 MORE articles and show that only the new rows trigger "
    "computation (do NOT re-create the table or re-insert existing rows)\n"
    "- Add a NEW computed column 'reading_time_minutes' (word_count / 200) "
    "AFTER data exists; it must populate all existing rows automatically\n"
    "- Query articles with negative sentiment via .where()\n"
    "- Files to create: app.py"
)


class U5IncrementalVerifier(StoryVerifier):

    @property
    def story_id(self) -> str:
        return "u5_incremental"

    @property
    def positive_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"import pixeltable|from pixeltable", "uses pixeltable"),
            (r"@pxt\.udf\b", "defines a UDF (word_count)"),
            (r"chat_completions", "uses an LLM computed column"),
            (r"keyword", "declares the keywords column"),
            (r"add_computed_column|TableModel|model_base", "declares computed columns"),
            (r"reading_time", "adds the late computed column"),
            (r"\.insert\s*\(", "inserts rows"),
            (r"\.where\s*\(|\.select\s*\(", "queries the result"),
        ]

    @property
    def negative_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"drop_table|pxt\.drop", "drops the table to force recomputation"),
            (r"if_exists\s*=\s*['\"]replace['\"]",
             "recreates the table with if_exists='replace' instead of incremental"),
            (r"for\s+\w+\s+in\s+.*:\s*\n\s*.*(?:openai|anthropic|client\.|chat_completions)",
             "imperative loop calling AI model"),
            (r"from langchain", "imports LangChain"),
            (r"import pandas|from pandas", "uses pandas as working store"),
            (r"import chromadb|import pinecone|import faiss", "separate vector store"),
        ]

    def functional_check(self, sandbox: PixeltableSandbox) -> dict:
        # exec_verification overwrites _eval_script.py, so preserve the
        # generated app for source-ordering evidence (same as u3/u4).
        script = sandbox.workdir / "_eval_script.py"
        if not script.exists():
            return {"pass": False, "reason": "no generated file to inspect"}
        (sandbox.workdir / "_generated_app.py").write_text(script.read_text())

        check_code = '''\
import json
from pathlib import Path

import pixeltable as pxt

try:
    tables = pxt.list_tables()
    arts = [t for t in tables if "article" in t.lower()]
    if not arts:
        print(json.dumps({"error": f"no articles table, found: {tables}"}))
    else:
        t = pxt.get_table(arts[0])
        meta = t.get_metadata()
        cols = meta["columns"]
        names = {n.lower(): n for n in cols}

        # "sentiment" contains the substring "time"; resolve it and the
        # other named columns first so rt cannot claim one of them.
        wc = next((n for k, n in names.items() if "word" in k or "count" in k), None)
        sent = next((n for k, n in names.items() if "sentiment" in k), None)
        kw = next((n for k, n in names.items() if "keyword" in k), None)
        rt = next((n for k, n in names.items() if "reading" in k), None)
        if not rt:
            rt = next(
                (n for k, n in names.items()
                 if "time" in k and n not in (wc, sent, kw)),
                None,
            )

        # Backfill proof comes from schema history, not final values: the
        # late column must carry a version_added newer than the initial
        # schema, so a column declared upfront cannot fake incremental work.
        initial_version = min(
            (m.get("version_added") or 0) for m in cols.values()
        )
        rt_meta = cols.get(rt) or {}

        # Ordering proof: schema versions only record post-creation adds,
        # not post-insert adds. The source must place the late column's
        # first mention after the first .insert( call.
        try:
            src = Path("_generated_app.py").read_text()
        except OSError:
            src = ""
        first_insert = src.find(".insert(")
        rt_decl = src.find(rt) if rt else -1

        out = {
            "table": arts[0],
            "columns": list(cols),
            "row_count": t.count(),
            "wc_col": wc,
            "wc_computed": bool(wc and cols[wc].get("is_computed")),
            "rt_col": rt,
            "rt_computed": bool(rt_meta.get("is_computed")),
            "rt_version_added": rt_meta.get("version_added"),
            "initial_version": initial_version,
            "late_after_insert": bool(rt and 0 <= first_insert < rt_decl),
            "insert_calls": src.count(".insert("),
            "sentiment_col": sent,
            "keywords_col": kw,
        }

        if wc and rt:
            df = t.select(t[wc], t[rt]).limit(200).collect().to_pandas()
            out["wc_nulls"] = int(df.iloc[:, 0].isna().sum())
            out["rt_nulls"] = int(df.iloc[:, 1].isna().sum())

        print(json.dumps(out))
except Exception as e:
    print(json.dumps({"error": str(e)[:300]}))
'''
        result = sandbox.exec_verification(check_code)

        if not result.success:
            return {"pass": False, "reason": f"verification failed: {result.stderr}"}

        try:
            data = json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, ValueError, IndexError):
            return {"pass": False, "reason": f"bad output: {result.stdout}"}

        if "error" in data:
            return {"pass": False, "reason": data["error"]}

        if (data.get("row_count") or 0) < 5:
            return {
                "pass": False,
                "reason": f"expected >= 5 rows across two insert waves, got {data.get('row_count')}",
            }
        if not data.get("wc_col") or not data.get("wc_computed"):
            return {"pass": False, "reason": "no computed word-count column found"}
        if not data.get("keywords_col"):
            return {"pass": False, "reason": "no keywords column found (prompt requires one)"}
        if not data.get("sentiment_col"):
            return {"pass": False, "reason": "no sentiment column found"}
        if not data.get("rt_col"):
            return {
                "pass": False,
                "reason": "no reading-time column added after data existed",
            }
        if not data.get("rt_computed"):
            return {
                "pass": False,
                "reason": "reading_time is not a computed column",
            }
        rt_version = data.get("rt_version_added")
        if rt_version is None or rt_version <= data.get("initial_version", 0):
            return {
                "pass": False,
                "reason": (
                    f"reading_time was part of the initial schema "
                    f"(version_added={rt_version}); the story requires "
                    f"adding it after data exists"
                ),
            }
        if not data.get("late_after_insert"):
            return {
                "pass": False,
                "reason": (
                    "reading_time is declared before any .insert( in the "
                    "generated source; the story requires adding it after "
                    "data exists"
                ),
            }
        if data.get("wc_nulls", 1) > 0:
            return {
                "pass": False,
                "reason": f"word_count unpopulated on {data['wc_nulls']} rows (second wave not computed?)",
            }
        if data.get("rt_nulls", 1) > 0:
            return {
                "pass": False,
                "reason": (
                    f"reading_time unpopulated on {data['rt_nulls']} rows; "
                    "a column added after data exists must backfill all rows"
                ),
            }

        return {
            "pass": True,
            "table": data.get("table"),
            "row_count": data.get("row_count"),
            "columns": data.get("columns", []),
            "sentiment_col": data.get("sentiment_col"),
        }
