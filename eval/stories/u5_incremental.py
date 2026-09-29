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
        check_code = '''\
import json

import pixeltable as pxt

try:
    tables = pxt.list_tables()
    arts = [t for t in tables if "article" in t.lower()]
    if not arts:
        print(json.dumps({"error": f"no articles table, found: {tables}"}))
    else:
        t = pxt.get_table(arts[0])
        cols = t.get_metadata()["columns"]
        names = {n.lower(): n for n in cols}

        wc = next((n for k, n in names.items() if "word" in k or "count" in k), None)
        rt = next((n for k, n in names.items() if "reading" in k or "time" in k), None)
        sent = next((n for k, n in names.items() if "sentiment" in k), None)

        out = {
            "table": arts[0],
            "columns": list(cols),
            "row_count": t.count(),
            "wc_col": wc,
            "rt_col": rt,
            "sentiment_col": sent,
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
        if not data.get("wc_col"):
            return {"pass": False, "reason": "no word-count computed column found"}
        if not data.get("rt_col"):
            return {
                "pass": False,
                "reason": "no reading-time column added after data existed",
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
