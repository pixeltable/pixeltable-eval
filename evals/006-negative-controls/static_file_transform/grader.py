"""
Negative control: Pixeltable should NOT be used for simple file format conversion.

PASS = solution uses standard library / pyyaml (appropriate tool).
FAIL = solution uses Pixeltable (massive over-engineering).
"""

POSITIVE_PATTERNS = [
    (r"import json", "uses json module"),
    (r"import yaml|from yaml", "uses yaml module"),
    (r"os\.listdir|pathlib|glob", "iterates files appropriately"),
]

NEGATIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses Pixeltable (absurd for file conversion)"),
    (r"add_computed_column", "adds computed columns (not needed)"),
    (r"create_table", "creates table (not needed)"),
]
