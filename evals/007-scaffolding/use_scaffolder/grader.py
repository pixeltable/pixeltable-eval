"""
Grader for use_scaffolder eval.

Checks that the agent uses an official scaffold path (pixeltable-new or
pxt init/example) and produces a TableModel + FastAPIRouter app that is
applied and served with the pxt CLI.
"""

POSITIVE_PATTERNS = [
    (r"uvx\s+pixeltable-new|pxt\s+init\b|pxt\s+(service|schema)\s+example",
     "scaffolds via pixeltable-new or pxt init/example"),
    (r"uv\s+sync", "installs dependencies with uv sync"),
    (r"TableModel|model_base\s*\(", "defines TableModel classes"),
    (r"document_splitter", "uses document_splitter for chunking"),
    (r"__indexes__|EmbeddingIndex", "declares embedding index on the model"),
    (r"\.similarity\s*\(", "uses similarity search"),
    (r"@pxt\.query\b", "defines a @pxt.query function"),
    (r"FastAPIRouter|pixeltable\.serving|add_query_route", "exposes the query via FastAPIRouter"),
    (r"pxt\s+schema\s+update", "applies schema with pxt schema update"),
    (r"pxt\s+service\s+update", "starts the service with pxt service update"),
]

NEGATIVE_PATTERNS = [
    (r"\bpxt\s+serve\b", "uses retired pxt serve CLI (does not exist)"),
    (r"\[+\s*tool\.pixeltable\.(serve|service)|\[\[\s*service(\.routes)?\s*\]\]",
     "writes TOML serve config (retired)"),
    (r"--backend\b|--serving\b|--batch\b", "uses removed pixeltable-new flags"),
    (r"pxt\.create_table\s*\(", "uses pxt.create_table in app code (use TableModel)"),
    (r"add_computed_column\s*\(", "uses add_computed_column in app code (declare on the model)"),
    (r"add_embedding_index\s*\(", "uses add_embedding_index in app code (use __indexes__)"),
    (r"from langchain|import chromadb|import pinecone|import faiss",
     "uses LangChain or a separate vector DB"),
    (r"from flask\s+import|from django", "uses Flask/Django instead of FastAPIRouter"),
    (r"uvicorn\.run\s*\(|app\.run\s*\(", "runs the server manually (use pxt service update)"),
]
