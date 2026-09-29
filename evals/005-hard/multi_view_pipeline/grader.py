"""
Grader for multi_view_pipeline eval.

Base table -> splitter view -> filtered view, each stage derived, with
if_exists='ignore' for idempotent reruns. No manual PDF parsing, no
re-materialization by hand.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.Document", "document column for the contracts"),
    (r"document_splitter", "chunks view via document_splitter"),
    (r"create_view|base\s*=|TableModel", "builds the view chain"),
    (r"if_exists\s*=\s*['\"]ignore['\"]", "idempotent table/view creation"),
    (r"add_embedding_index|__indexes__|EmbeddingIndex", "embedding index on the clauses view"),
    (r"chat_completions|clause_type|risk_score", "LLM classification + dependent score column"),
    (r"@pxt\.query|\.similarity\s*\(", "query function over clauses"),
]

NEGATIVE_PATTERNS = [
    (r"PyPDF2|pdfplumber|import fitz|pypdf", "manual PDF parsing (use document_splitter)"),
    (r"for\s+\w+\s+in\s+.*:\s*\n\s*.*(?:openai|chat_completions|anthropic|client\.)",
     "imperative loop calling AI model"),
    (r"from pixeltable\.iterators\s+import", "deprecated pixeltable.iterators shim"),
    (r"from langchain|from llama_index", "imports an AI framework"),
    (r"import pandas|from pandas", "uses pandas as working store"),
]
