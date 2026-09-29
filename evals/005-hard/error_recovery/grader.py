"""
Grader for error_recovery eval.

Per-row failure is modeled by nullable UDF returns and errortype/errormsg,
not by try/except around the whole pipeline.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"@pxt\.udf\b", "defines a fetch UDF"),
    (r"str\s*\|\s*None|Optional\[|->\s*None|\|\s*None\s*=", "nullable return annotation on the UDF"),
    (r"fetched", "declares the fetched computed column"),
    (r"chat_completions|summary", "summary computed column"),
    (r"\.insert\s*\(", "inserts the URL mix"),
    (r"\.where\s*\(", "filters to successful fetches"),
    (r"errortype|errormsg|\.revert\s*\(", "inspects cell errors or reverts"),
]

NEGATIVE_PATTERNS = [
    (r"try\s*:\s*\n\s*(?:import pixeltable.*\n)?\s*.*create_table",
     "try/except around pipeline construction (must be per-row)"),
    (r"except\s*:\s*(?:pass|\n)", "bare except swallowing all errors"),
    (r"from langchain|from llama_index", "imports an AI framework"),
    (r"import pandas|from pandas", "uses pandas as working store"),
]
