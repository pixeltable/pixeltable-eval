"""
U3: Serving a pipeline with pxt service

Prompt: "Build a Pixeltable-powered REST API for movie review analysis."

Verifier checks:
- Static: uses TableModel, FastAPIRouter routes, computed columns,
  pxt schema update + pxt service update
- Negative: no retired pxt serve CLI / TOML routes, no hand-rolled server,
  no notebook APIs in app code
- Functional: `pxt init` + `pxt schema update` materializes a reviews table
  with sentiment and summary computed columns
"""

from __future__ import annotations

import json

from eval.sandbox import PixeltableSandbox
from eval.verifier import StoryVerifier


PROMPT = (
    "Build a Pixeltable-powered REST API that serves a movie review analysis "
    "pipeline.\n\n"
    "Requirements:\n"
    "- Write app.py using TableModel (pxt.model_base()): a table 'reviews' "
    "with columns title (pxt.String) and review_text (pxt.String)\n"
    "- Add computed columns using OpenAI chat_completions:\n"
    "  - sentiment: classifies the review as positive/negative/neutral\n"
    "  - summary: generates a one-sentence summary of the review\n"
    "- Expose an insert route at /analyze with FastAPIRouter "
    "(from pixeltable.serving) that takes title and review_text and returns "
    "title, sentiment, and summary\n"
    "- Give me the commands to create the tables and start the service with "
    "the pxt CLI"
)


class U3ServiceVerifier(StoryVerifier):

    @property
    def story_id(self) -> str:
        return "u3_service"

    @property
    def positive_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"import pixeltable|from pixeltable", "uses pixeltable"),
            (r"TableModel|model_base\s*\(", "defines a TableModel"),
            (r"FastAPIRouter|from pixeltable\.serving", "uses FastAPIRouter"),
            (r"add_insert_route|add_compute_route|insert_route\s*\(",
             "declares an insert/compute route"),
            (r"chat_completions|messages", "calls an LLM"),
            (r"\.choices\[0\]\.message\.content", "extracts OpenAI response correctly"),
            (r"pxt\s+schema\s+update", "applies schema with pxt schema update"),
            (r"pxt\s+service\s+update", "starts service with pxt service update"),
        ]

    @property
    def negative_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"\bpxt\s+serve\b", "uses retired pxt serve CLI (does not exist)"),
            (r"\[+\s*tool\.pixeltable\.(serve|service)|\[\[\s*service(\.routes)?\s*\]\]",
             "writes TOML serve config (retired)"),
            (r"pxt\.create_table\s*\(", "uses pxt.create_table in app code (use TableModel)"),
            (r"add_computed_column\s*\(", "uses add_computed_column in app code (declare on the model)"),
            (r"uvicorn\.run\s*\(|app\.run\s*\(", "runs the server manually (use pxt service update)"),
            (r"from flask\s+import|from django", "uses Flask/Django instead of FastAPIRouter"),
            (r"from langchain", "imports LangChain"),
            (r"import pandas|from pandas", "uses pandas as working store"),
            (r"modules\s*=\s*\[", "writes a TOML modules list (retired field)"),
        ]

    def functional_check(self, sandbox: PixeltableSandbox) -> dict:
        # exec_verification overwrites _eval_script.py with the check script,
        # so preserve the generated code as app.py first.
        script = sandbox.workdir / "_eval_script.py"
        if not script.exists():
            return {"pass": False, "reason": "no generated file to apply"}
        (sandbox.workdir / "app.py").write_text(script.read_text())

        check_code = """\
import json
import subprocess
import sys


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=240)


try:
    sh(["pxt", "init"])
    upd = sh(["pxt", "schema", "update", "app.py", "eval_app", "-f"])
    if upd.returncode != 0:
        print(json.dumps({"error": f"pxt schema update failed: {upd.stderr[-300:]}"}))
        sys.exit(0)

    import pixeltable as pxt
    tables = pxt.list_tables()
    review_tables = [t for t in tables if t.startswith("eval_app.") and "review" in t.lower()]
    if not review_tables:
        review_tables = [t for t in tables if "review" in t.lower()]
    if not review_tables:
        print(json.dumps({"error": f"no reviews table, found: {tables}"}))
        sys.exit(0)

    t = pxt.get_table(review_tables[0])
    cols = t.get_metadata()["columns"]
    print(json.dumps({
        "columns": list(cols),
        "has_sentiment": any(
            "sentiment" in name.lower() and meta.get("is_computed")
            for name, meta in cols.items()
        ),
        "has_summary": any(
            "summar" in name.lower() and meta.get("is_computed")
            for name, meta in cols.items()
        ),
    }))
except FileNotFoundError:
    print(json.dumps({"error": "pxt CLI not on PATH"}))
except Exception as e:
    print(json.dumps({"error": str(e)[:300]}))
"""
        result = sandbox.exec_verification(check_code)

        if not result.success:
            return {"pass": False, "reason": f"verification failed: {result.stderr}"}

        try:
            data = json.loads(result.stdout.strip())
        except (json.JSONDecodeError, ValueError):
            return {"pass": False, "reason": f"bad output: {result.stdout}"}

        if "error" in data:
            if "pxt CLI not on PATH" in data["error"]:
                return {"pass": None, "skipped": True, "reason": data["error"]}
            return {"pass": False, "reason": data["error"]}

        if not data.get("has_sentiment"):
            return {"pass": False, "reason": "missing sentiment computed column"}
        if not data.get("has_summary"):
            return {"pass": False, "reason": "missing summary computed column"}

        return {
            "pass": True,
            "columns": data.get("columns", []),
        }
