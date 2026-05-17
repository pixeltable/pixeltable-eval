"""
U2: Project Scaffolding with pixeltable-new

Prompt: "Start a new Pixeltable backend project using the scaffolder and configure
a semantic search API."

Verifier checks:
- Static: uses pixeltable-new, uv sync, embedding index, pxt serve config
- Negative: no manual project creation, no LangChain/Flask
- Functional: scaffolded files exist, schema imports work
"""

from __future__ import annotations

from eval.sandbox import PixeltableSandbox
from eval.verifier import StoryVerifier


PROMPT = (
    "I want to start a new Pixeltable project that provides a REST API for "
    "semantic search over documents.\n\n"
    "Requirements:\n"
    "- Use `uvx pixeltable-new` to scaffold the project (do NOT build from scratch)\n"
    "- Choose the 'backend' pattern (it includes a FastAPI serving layer)\n"
    "- The project name should be 'doc-search'\n"
    "- After scaffolding, install dependencies with `uv sync`\n"
    "- Create a schema.py that defines a documents table with: path (pxt.Document), "
    "a chunks view with document_splitter, an embedding index on the chunks, "
    "and a @pxt.query function for semantic search\n"
    "- Configure pyproject.toml [tool.pixeltable.serve] to expose the query as a REST endpoint\n"
    "- Show the commands to initialize the schema and start the server"
)


class U2ScaffoldingVerifier(StoryVerifier):

    @property
    def story_id(self) -> str:
        return "u2_scaffolding"

    @property
    def positive_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"uvx\s+pixeltable-new|pixeltable.new", "uses pixeltable-new scaffolder"),
            (r"--backend|backend", "selects backend pattern"),
            (r"uv\s+sync", "installs dependencies with uv"),
            (r"add_embedding_index\s*\(", "creates embedding index"),
            (r"\.similarity\s*\(", "uses similarity search"),
            (r"@pxt\.(query|udf)\b", "defines query or UDF function"),
            (r"document_splitter|DocumentSplitter", "uses document splitter"),
            (r"\[tool\.pixeltable", "configures pixeltable in pyproject.toml"),
            (r"pxt\s+serve", "runs pxt serve"),
        ]

    @property
    def negative_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"pip\s+install\s+pixeltable", "manually installs pixeltable (should use scaffolder)"),
            (r"from langchain", "imports LangChain"),
            (r"import chromadb", "imports ChromaDB"),
            (r"import pinecone", "imports Pinecone"),
            (r"import faiss", "imports FAISS"),
            (r"from flask\s+import|from django", "uses Flask/Django instead of pxt serve"),
            (r"mkdir\s.*&&.*touch\s", "manually creates project structure"),
        ]
