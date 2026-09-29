"""
Grader for computed_columns eval.

The point: three computed columns (two LLM, one UDF) that run on insert,
not a loop over rows. EXECUTE_CODE runs the generated app in the sandbox.
"""

EXECUTE_CODE = True

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.create_table|TableModel|model_base", "creates the reviews table"),
    (r"\.insert\s*\(", "inserts sample reviews"),
    (r"chat_completions", "uses OpenAI chat_completions"),
    (r"sentiment", "declares the sentiment computed column"),
    (r"summary", "declares the summary computed column"),
    (r"@pxt\.udf\b|word_count", "defines the word_count UDF"),
    (r"\.where\s*\(|\.select\s*\(|rating\s*>=\s*4", "queries rating >= 4"),
]

NEGATIVE_PATTERNS = [
    (r"for\s+\w+\s+in\s+.*:\s*\n\s*.*(?:openai|chat_completions|anthropic|client\.)",
     "imperative loop calling AI model (use computed columns)"),
    (r"from langchain|from llama_index", "imports an AI framework"),
    (r"import pandas|from pandas", "uses pandas as working store"),
    (r"import sqlite3|import psycopg2", "hand-rolls SQL storage"),
    (r"def\s+\w+\([^)]*\)\s*:\s*\n\s*return\s+.*openai|requests\.post.*api\.openai",
     "hand-calls OpenAI instead of pixeltable.functions"),
]
