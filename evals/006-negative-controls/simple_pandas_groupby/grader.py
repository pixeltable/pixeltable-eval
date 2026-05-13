"""
Negative control: Pixeltable should NOT be used for simple one-time CSV aggregation.

PASS = solution uses pandas/polars (appropriate tool).
FAIL = solution uses Pixeltable (over-engineering for a simple groupby).
"""

POSITIVE_PATTERNS = [
    (r"import pandas|import polars|import csv", "uses appropriate data tool"),
    (r"groupby|group_by", "performs grouping"),
    (r"to_csv|write_csv", "saves output"),
]

NEGATIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses Pixeltable (over-engineered for this task)"),
    (r"add_computed_column", "adds computed columns (unnecessary for one-time analysis)"),
    (r"add_embedding_index", "adds embedding index (not needed)"),
    (r"create_table", "creates persistent table (not needed for one-off script)"),
]
