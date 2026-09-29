"""
Grader for computed_not_loop eval.

All three AI transformations must be computed columns that run on insert.
A for-loop calling OpenAI per row is exactly the anti-pattern this eval
exists to catch.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.create_table|TableModel|model_base", "creates the headlines table"),
    (r"\.insert\s*\(", "inserts sample headlines"),
    (r"chat_completions", "uses OpenAI chat_completions"),
    (r"add_computed_column|categor|tweet|clickbait",
     "declares the three transformation columns"),
    (r"\.choices\[0\]\.message\.content", "extracts the OpenAI response correctly"),
    (r"\.select\s*\(|\.collect\s*\(", "queries results"),
]

NEGATIVE_PATTERNS = [
    (r"for\s+\w+\s+in\s+.*:\s*\n\s*.*(?:openai|chat_completions|anthropic|client\.)",
     "imperative loop calling AI model (the anti-pattern under test)"),
    (r"from langchain|from llama_index", "imports an AI framework"),
    (r"import pandas|from pandas", "uses pandas as working store"),
    (r"\.apply\s*\(", "DataFrame.apply for AI calls (use computed columns)"),
]
