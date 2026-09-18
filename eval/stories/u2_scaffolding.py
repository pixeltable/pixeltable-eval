"""
U2: Project Scaffolding

Prompt: "Start a new Pixeltable project that serves a semantic search API
over my documents."

Verifier checks:
- Static: uses an official scaffold path (pixeltable-new or pxt init/example),
  TableModel, document_splitter view, __indexes__, @pxt.query, FastAPIRouter,
  pxt schema update + pxt service update
- Negative: no retired pxt serve CLI / TOML routes, no removed scaffolder
  flags, no notebook APIs in app code, no LangChain/vector DBs
- Functional: skipped (scaffolding is verified statically; the sandbox does
  not run agent shell commands)
"""

from __future__ import annotations

from eval.sandbox import PixeltableSandbox
from eval.verifier import StoryVerifier


PROMPT = (
    "I want to start a new Pixeltable project that provides a REST API for "
    "semantic search over documents.\n\n"
    "Requirements:\n"
    "- Scaffold the project with `uvx pixeltable-new` or `pxt init` + "
    "`pxt service example` (do NOT build the project structure by hand)\n"
    "- The project name should be 'doc-search'\n"
    "- Install dependencies with `uv sync`\n"
    "- Edit app.py so it defines a documents table (TableModel) with: a path "
    "column (pxt.Document), a chunks view built with document_splitter, an "
    "embedding index declared on the model, and a @pxt.query function for "
    "semantic search exposed through a FastAPIRouter query route\n"
    "- Show the commands to create the tables and start the service"
)


class U2ScaffoldingVerifier(StoryVerifier):

    @property
    def story_id(self) -> str:
        return "u2_scaffolding"

    @property
    def positive_patterns(self) -> list[tuple[str, str]]:
        return [
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

    @property
    def negative_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"\bpxt\s+serve\b", "uses retired pxt serve CLI (does not exist)"),
            (r"\[+\s*tool\.pixeltable\.(serve|service)|\[\[\s*service(\.routes)?\s*\]\]",
             "writes TOML serve config (retired)"),
            (r"pixeltable-new[^\n]*--(backend|serving|batch)\b",
             "uses removed pixeltable-new flags"),
            (r"pxt\.create_table\s*\(", "uses pxt.create_table in app code (use TableModel)"),
            (r"add_computed_column\s*\(", "uses add_computed_column in app code (declare on the model)"),
            (r"add_embedding_index\s*\(", "uses add_embedding_index in app code (use __indexes__)"),
            (r"from langchain|import chromadb|import pinecone|import faiss",
             "uses LangChain or a separate vector DB"),
            (r"from flask\s+import|from django", "uses Flask/Django instead of FastAPIRouter"),
            (r"uvicorn\.run\s*\(|app\.run\s*\(", "runs the server manually (use pxt service update)"),
        ]

    def functional_check(self, sandbox: PixeltableSandbox) -> dict:
        return {"pass": None, "skipped": True, "reason": "scaffolding is verified statically"}
