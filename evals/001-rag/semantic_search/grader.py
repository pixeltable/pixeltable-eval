"""
Grader for semantic_search eval.

Embedding index + similarity() + an LLM computed column; no vector DB,
no manual similarity math.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.create_table|TableModel|model_base|'papers|\"papers|research",
     "creates the papers table"),
    (r"\.insert\s*\(", "inserts sample papers"),
    (r"add_embedding_index|__indexes__|EmbeddingIndex", "declares an embedding index on abstract"),
    (r"\.similarity\s*\(", "search function uses .similarity()"),
    (r"chat_completions|keywords", "computed column generating keywords"),
]

NEGATIVE_PATTERNS = [
    (r"import chromadb|import pinecone|import faiss|from qdrant",
     "separate vector database (use add_embedding_index)"),
    (r"cosine_similarity|np\.dot|sklearn", "manual vector math (use .similarity)"),
    (r"from langchain|from llama_index", "imports an AI framework"),
    (r"for\s+\w+\s+in\s+.*:\s*\n\s*.*(?:openai|chat_completions|client\.)",
     "imperative loop calling AI model"),
    (r"import pandas|from pandas", "uses pandas as working store"),
]
