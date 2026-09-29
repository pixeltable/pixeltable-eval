"""
Grader for embedding_index eval.

Semantic search must come from a Pixeltable embedding index + similarity(),
not a separate vector DB or manual cosine math.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.create_table|TableModel|model_base|'faq|\"faq", "creates the faq table"),
    (r"\.insert\s*\(", "inserts FAQ entries"),
    (r"add_embedding_index|__indexes__|EmbeddingIndex", "declares an embedding index"),
    (r"openai|text_embedding|embedding", "uses an embedding function"),
    (r"\.similarity\s*\(", "queries with .similarity()"),
    (r"@pxt\.query|def\s+\w*search|limit\s*\(\s*3\s*\)", "search function returning top 3"),
]

NEGATIVE_PATTERNS = [
    (r"import chromadb|import pinecone|import faiss|from qdrant|import weaviate",
     "separate vector database (use add_embedding_index)"),
    (r"cosine_similarity|np\.dot|\.dot\s*\(|sklearn", "manual vector math (use .similarity)"),
    (r"from langchain|from llama_index", "imports an AI framework"),
    (r"\.similarity\(\s*['\"]", ".similarity() positional string (use string= kwarg)"),
    (r"import pandas|from pandas", "uses pandas as working store"),
]
