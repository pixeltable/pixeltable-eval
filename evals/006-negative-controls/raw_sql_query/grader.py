"""
Negative control: Pixeltable should NOT be used for direct SQL reporting.

PASS = solution uses psycopg2/sqlalchemy (appropriate tool).
FAIL = solution uses Pixeltable (wrong tool for direct DB queries).
"""

POSITIVE_PATTERNS = [
    (r"import psycopg2|from sqlalchemy|import sqlite3", "uses database driver"),
    (r"connect\(|create_engine\(", "connects to database"),
    (r"SELECT|execute\(", "runs SQL query"),
]

NEGATIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses Pixeltable (wrong tool for SQL reporting)"),
    (r"add_computed_column", "adds computed columns (not needed)"),
    (r"add_embedding_index", "adds embedding index (not needed)"),
]
