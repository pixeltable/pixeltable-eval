"""
Grader for no_pandas_store eval.

Pandas is allowed (and expected) for CSV ingest and final export; the
anti-pattern is pandas as the working store mid-pipeline — DataFrame.apply
for AI calls, or skipping the table entirely.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.create_table|TableModel|model_base|pxt\.io\.import",
     "data lands in a pixeltable table"),
    (r"chat_completions|sentiment", "sentiment computed column via an LLM"),
    (r"summary", "summary computed column"),
    (r"\.where\s*\(|\.select\s*\(|\.filter\s*\(", "filters reviews by sentiment"),
    (r"to_pandas\s*\(\)", "exports to pandas at the end"),
]

NEGATIVE_PATTERNS = [
    (r"\.apply\s*\(", "DataFrame.apply for AI calls (use computed columns)"),
    (r"for\s+\w+\s+in\s+(df\.|.*iterrows|.*itertuples)", "iterates a DataFrame calling models"),
    (r"df\[(['\"])(sentiment|summary)\1\]\s*=", "writes AI results into the DataFrame"),
    (r"import sqlite3|import psycopg2", "hand-rolls SQL storage"),
    (r"from langchain|from llama_index", "imports an AI framework"),
]
