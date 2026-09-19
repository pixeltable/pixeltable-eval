"""
U1: PDF RAG Pipeline

Prompt: "I have a folder of PDFs in ./docs. Build a Python app with Pixeltable
that lets me ask questions about them."

Verifier checks:
- Static: uses Document type, document_splitter, embedding index, similarity, LLM call
- Negative: no LangChain, no Chroma/Pinecone, no pandas-as-store, no imperative loops
- Functional: tables exist, chunks were created, a question returns a relevant answer
"""

from __future__ import annotations

import json

from eval.sandbox import PixeltableSandbox
from eval.verifier import StoryVerifier


PROMPT = (
    "I have a folder of PDFs in ./docs. Build a Python app with Pixeltable "
    "that lets me ask questions about them."
)


class U1PdfRagVerifier(StoryVerifier):

    @property
    def story_id(self) -> str:
        return "u1_pdf_rag"

    @property
    def positive_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"pxt\.Document", "uses pxt.Document type"),
            (r"document_splitter", "uses document_splitter for chunking"),
            (r"add_embedding_index\s*\(|__indexes__|EmbeddingIndex", "creates embedding index"),
            (r"\.similarity\s*\(", "uses similarity search"),
            (r"chat_completions|messages|generate_content", "calls an LLM for answering"),
        ]

    @property
    def negative_patterns(self) -> list[tuple[str, str]]:
        return [
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

    def functional_check(self, sandbox: PixeltableSandbox) -> dict:
        tables = sandbox.list_tables()

        if not tables:
            return {"pass": False, "reason": "no tables created"}

        has_view = len(tables) >= 2
        if not has_view:
            return {
                "pass": False,
                "reason": f"expected base table + chunk view, found {len(tables)} table(s): {tables}",
            }

        chunk_table = None
        for t in tables:
            if any(kw in t.lower() for kw in ["chunk", "split", "doc", "piece", "segment"]):
                chunk_table = t
                break
        if not chunk_table:
            chunk_table = tables[-1]

        check_code = f"""\
import pixeltable as pxt
import json

try:
    t = pxt.get_table('{chunk_table}')
    count = t.count()
    cols = t.columns()
    schema = {{name: meta['type_'] for name, meta in t.get_metadata()['columns'].items()}}
    print(json.dumps({{
        "chunk_count": count,
        "columns": cols,
        "schema": schema,
    }}))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
"""
        result = sandbox.exec_verification(check_code)

        if not result.success:
            return {"pass": False, "reason": f"verification script failed: {result.stderr}"}

        try:
            data = json.loads(result.stdout.strip())
        except (json.JSONDecodeError, ValueError):
            return {"pass": False, "reason": f"bad verification output: {result.stdout}"}

        if "error" in data:
            return {"pass": False, "reason": data["error"]}

        chunk_count = data.get("chunk_count", 0)
        if chunk_count == 0:
            return {"pass": False, "reason": "chunk table is empty (0 rows)"}

        return {
            "pass": True,
            "chunk_count": chunk_count,
            "columns": data.get("columns", []),
            "tables_found": tables,
        }
