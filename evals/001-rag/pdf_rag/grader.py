"""
Grader for pdf_rag eval.

Static checks: correct Pixeltable patterns present, no anti-patterns.
Functional check (optional): tables created with chunks, embedding index exists.
"""

POSITIVE_PATTERNS = [
    (r"pxt\.Document", "uses pxt.Document type"),
    (r"document_splitter", "uses document_splitter for chunking"),
    (r"add_embedding_index\s*\(", "creates embedding index"),
    (r"\.similarity\s*\(", "uses similarity search"),
    (r"chat_completions|messages|generate_content", "calls an LLM for answering"),
]

NEGATIVE_PATTERNS = [
    (r"from langchain", "imports LangChain"),
    (r"from llama_index", "imports LlamaIndex"),
    (r"from haystack", "imports Haystack"),
    (r"import chromadb", "imports ChromaDB"),
    (r"import pinecone", "imports Pinecone"),
    (r"import faiss", "imports FAISS"),
    (r"from qdrant", "imports Qdrant"),
    (r"import pandas|from pandas", "uses pandas as working store"),
    (
        r"for\s+\w+\s+in\s+.*:\s*\n\s*.*(?:openai|anthropic|client\.)",
        "imperative loop calling AI model",
    ),
]
