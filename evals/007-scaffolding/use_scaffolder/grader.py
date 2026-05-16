"""
Grader for use_scaffolder eval.

Checks that the agent uses pixeltable-new to scaffold and produces
a valid schema + serving configuration.
"""

POSITIVE_PATTERNS = [
    (r"uvx\s+pixeltable-new|pixeltable.new", "uses pixeltable-new scaffolder"),
    (r"--backend|backend", "selects backend pattern"),
    (r"uv\s+sync", "installs dependencies with uv"),
    (r"add_embedding_index\s*\(", "creates embedding index"),
    (r"\.similarity\s*\(", "uses similarity search"),
    (r"@pxt\.(query|udf)\b", "defines query or UDF function"),
    (r"document_splitter|DocumentSplitter", "uses document splitter"),
    (r"\[tool\.pixeltable", "configures pixeltable in pyproject.toml"),
    (r"pxt\s+serve|pxt\.serve", "runs pxt serve"),
]

NEGATIVE_PATTERNS = [
    (r"pip\s+install\s+pixeltable", "manually installs pixeltable (should use scaffolder)"),
    (r"from langchain", "imports LangChain"),
    (r"import chromadb", "imports ChromaDB"),
    (r"import pinecone", "imports Pinecone"),
    (r"import faiss", "imports FAISS"),
    (r"from flask\s+import|from django", "uses Flask/Django instead of pxt serve"),
    (r"mkdir\s.*&&.*touch\s", "manually creates project structure"),
]
