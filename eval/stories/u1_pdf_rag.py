"""
U1: PDF RAG Pipeline

Prompt: "I have a folder of PDFs in ./docs. Build a Python app with Pixeltable
that lets me ask questions about them."

Verifier checks:
- Static: uses Document type, document_splitter, embedding index, similarity, LLM call
- Negative: no LangChain, no Chroma/Pinecone, no pandas-as-store, no imperative loops
- Functional: schema materializes (imperative or TableModel style), fixture
  PDFs are ingested, a chunk view contains rows, and a similarity query over
  the chunks actually executes (proving an embedding index exists)
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
        # exec_verification overwrites _eval_script.py with the check script,
        # so preserve the generated code as app.py for pxt schema update
        # (same path u3's check takes).
        script = sandbox.workdir / "_eval_script.py"
        if not script.exists():
            return {"pass": False, "reason": "no generated file to apply"}
        (sandbox.workdir / "app.py").write_text(script.read_text())

        check_code = """\
import glob
import json
import subprocess
import sys
from pathlib import Path

import pixeltable as pxt

# Use the pxt binary from the same interpreter as this script; a different
# pxt on PATH may run a different pixeltable version.
pxtc = Path(sys.executable).parent / "pxt"
pxtc = str(pxtc) if pxtc.exists() else "pxt"

try:
    tables = pxt.list_tables()
    if not tables:
        # TableModel-style answers only declare classes; materialize them.
        try:
            subprocess.run([pxtc, "init"], capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            print(json.dumps({"error": "pxt CLI not on PATH"}))
            sys.exit(0)
        upd = subprocess.run(
            [pxtc, "schema", "update", "app.py", "eval_app", "-f"],
            capture_output=True, text=True, timeout=240,
        )
        if upd.returncode != 0:
            print(json.dumps({"error": f"pxt schema update failed: {upd.stderr[-300:]}"}))
            sys.exit(0)
        tables = pxt.list_tables()

    base = None
    views = []
    others = []
    for name in tables:
        t = pxt.get_table(name)
        meta = t.get_metadata()
        doc_col = next(
            (c for c, m in meta["columns"].items()
             if "document" in str(m.get("type_", "")).lower()),
            None,
        )
        if meta.get("is_view"):
            views.append(t)
        elif doc_col is not None and base is None:
            base = (t, doc_col, meta["columns"])
        else:
            others.append(t)

    # Schema-only answers leave the base empty; insert the fixture PDFs so
    # the chunk pipeline actually runs. Required scalar columns get simple
    # defaults (the file path for strings) so declared-but-unused columns
    # do not block the insert.
    if base is not None and base[0].count() == 0:
        t, doc_col, cols = base
        pdfs = sorted(glob.glob("docs/*.pdf"))
        rows = []
        for i, p in enumerate(pdfs):
            row = {doc_col: p}
            for c, m in cols.items():
                typ = str(m.get("type_", "")).lower()
                if c == doc_col or "| none" in typ or m.get("is_computed"):
                    continue
                defaults = {"string": p, "int": i, "float": 0.0, "bool": False}
                if typ in defaults:
                    row[c] = defaults[typ]
            rows.append(row)
        if rows:
            t.insert(rows)

    candidates = views or others
    chunk_count = max((t.count() for t in candidates), default=None)

    # Prove the query path works end to end: similarity() only resolves when
    # the column carries a live embedding index, and running it exercises the
    # embed function on the query string. Provider auth failures are recorded
    # as env issues, not app defects.
    sim_ok = False
    sim_auth = False
    sim_err = None
    sim_col = None
    probes = list(candidates) + ([base[0]] if base else [])
    for cand in probes:
        meta = cand.get_metadata()
        for cname, m in meta["columns"].items():
            if "string" not in str(m.get("type_", "")).lower():
                continue
            try:
                sim = cand[cname].similarity(string="test query")
                cand.order_by(sim, asc=False).limit(1).collect()
                sim_ok, sim_col = True, cname
                break
            except Exception as e:
                msg = str(e).lower()
                if any(k in msg for k in ("api_key", "api key", "401", "authentication", "unauthorized")):
                    sim_auth = True
                else:
                    sim_err = str(e)[:200]
        if sim_ok or sim_auth:
            break

    print(json.dumps({
        "tables": tables,
        "chunk_count": chunk_count,
        "similarity_ok": sim_ok,
        "similarity_auth_skip": sim_auth,
        "similarity_column": sim_col,
        "similarity_error": sim_err,
    }))
except Exception as e:
    print(json.dumps({"error": str(e)[:300]}))
"""
        result = sandbox.exec_verification(check_code)

        if not result.success:
            return {"pass": False, "reason": f"verification script failed: {result.stderr}"}

        try:
            # pxt prints a connection banner to stdout; the JSON payload is
            # always the last line.
            data = json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, ValueError, IndexError):
            return {"pass": False, "reason": f"bad verification output: {result.stdout}"}

        if "error" in data:
            if "pxt CLI not on PATH" in data["error"]:
                return {"pass": None, "skipped": True, "reason": data["error"]}
            return {"pass": False, "reason": data["error"]}

        tables = data.get("tables", [])
        if len(tables) < 2:
            return {
                "pass": False,
                "reason": f"expected base table + chunk view, found {len(tables)} table(s): {tables}",
            }
        chunk_count = data.get("chunk_count")
        if chunk_count is None:
            return {"pass": False, "reason": "no chunk view or second table found"}
        if chunk_count == 0:
            return {"pass": False, "reason": "chunk table is empty (0 rows)"}
        if not (data.get("similarity_ok") or data.get("similarity_auth_skip")):
            return {
                "pass": False,
                "reason": f"similarity query does not run: {data.get('similarity_error')}",
                "chunk_count": chunk_count,
            }

        return {
            "pass": True,
            "chunk_count": chunk_count,
            "tables_found": tables,
            "similarity_column": data.get("similarity_column"),
            "similarity_auth_skip": data.get("similarity_auth_skip"),
        }
