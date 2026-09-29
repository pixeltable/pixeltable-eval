"""
Grader for no_langchain eval.

Chunking is an iterator view, embeddings are a table index, search is
similarity() — the LangChain stack must not appear.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"document_splitter|string_splitter", "chunks via an iterator function"),
    (r"create_view|base\s*=|TableModel", "builds the chunks view"),
    (r"add_embedding_index|__indexes__|EmbeddingIndex", "declares an embedding index"),
    (r"\.similarity\s*\(", "search uses .similarity()"),
    (r"@pxt\.query|def\s+\w*search|limit\s*\(\s*5\s*\)", "query function returning top 5"),
    (r"\.insert\s*\(", "inserts sample documents"),
]

NEGATIVE_PATTERNS = [
    (r"from langchain|import langchain|RecursiveCharacterTextSplitter",
     "imports LangChain (the anti-pattern under test)"),
    (r"from llama_index|from haystack", "imports another AI framework"),
    (r"import chromadb|import pinecone|import faiss|from qdrant",
     "separate vector database"),
    (r"from pixeltable\.iterators\s+import", "deprecated pixeltable.iterators shim"),
    (r"import pandas|from pandas", "uses pandas as working store"),
]
