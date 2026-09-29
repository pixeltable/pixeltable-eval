"""
Grader for create_table eval.

The table must be real Pixeltable storage with a computed column, not a
hand-rolled store. EXECUTE_CODE runs the generated app in the sandbox:
schema-level mistakes (bad types, missing functions) fail loudly, while
provider-dependent computed cells degrade to recorded row errors.
"""

EXECUTE_CODE = True

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.create_dir|create_dir\s*\(|TableModel|model_base|'shop|\"shop",
     "creates the shop namespace / declares models"),
    (r"pxt\.create_table|TableModel", "creates the products table"),
    (r"pxt\.Image|Image", "declares an image column"),
    (r"\.insert\s*\(", "inserts sample products"),
    (r"chat_completions|add_computed_column|=\s*pxtf\.|@pxt\.udf|tagline",
     "adds a computed column for the tagline"),
    (r"\.where\s*\(|\.select\s*\(|\.filter\s*\(", "queries products under $50"),
]

NEGATIVE_PATTERNS = [
    (r"import sqlite3|import psycopg2|create_engine", "hand-rolls SQL storage"),
    (r"from langchain|from llama_index|from haystack", "imports an AI framework"),
    (r"import chromadb|import pinecone|import faiss", "separate vector store"),
    (r"\.to_csv\s*\(|json\.dump.*products|pickle\.dump", "stores data in flat files"),
    (r"for\s+\w+\s+in\s+.*:\s*\n\s*.*(?:openai|chat_completions|client\.)",
     "imperative loop calling AI model"),
]
