"""
Grader for incremental_update eval.

Two insert waves and a column added after data exists. The anti-patterns:
recreating the table or re-inserting old rows to force recomputation.
EXECUTE_CODE runs the pipeline in the sandbox.
"""

EXECUTE_CODE = True

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.create_table|TableModel|model_base|'analytics|\"analytics",
     "creates the articles table"),
    (r"@pxt\.udf\b|word_count", "word_count via a UDF"),
    (r"chat_completions|sentiment|keywords", "LLM computed columns"),
    (r"\.insert\s*\(", "inserts articles"),
    (r"add_computed_column|reading_time", "adds a column after data exists"),
    (r"\.where\s*\(|\.select\s*\(", "queries negative sentiment"),
]

NEGATIVE_PATTERNS = [
    (r"drop_table|pxt\.drop", "drops the table to force recomputation"),
    (r"if_exists\s*=\s*['\"]replace['\"]", "recreates the table instead of updating"),
    (r"for\s+\w+\s+in\s+.*:\s*\n\s*.*(?:openai|chat_completions|anthropic|client\.)",
     "imperative loop calling AI model"),
    (r"from langchain|from llama_index", "imports an AI framework"),
    (r"import pandas|from pandas", "uses pandas as working store"),
]
