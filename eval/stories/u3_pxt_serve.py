"""
U3: pxt serve Configuration

Prompt: "Build a Pixeltable-powered REST API for movie review analysis using pxt serve."

Verifier checks:
- Static: uses @pxt.query, [tool.pixeltable.serve], colon notation, computed columns
- Negative: no manual FastAPI/Flask, no dot notation for serve queries
- Functional: schema module exists, pyproject.toml has serve config
"""

from __future__ import annotations

import json

from eval.sandbox import PixeltableSandbox
from eval.verifier import StoryVerifier


PROMPT = (
    "Build a Pixeltable-powered REST API that serves a movie review analysis pipeline.\n\n"
    "Requirements:\n"
    "- Create a table 'movies/reviews' with columns: title (string), review_text (string)\n"
    "- Add computed columns using OpenAI:\n"
    "  - sentiment: classifies the review as positive/negative/neutral\n"
    "  - summary: generates a one-sentence summary of the review\n"
    "- Create a @pxt.query function called 'analyze_review' that takes a title and "
    "review_text, inserts the row, waits for computed columns, and returns the analysis\n"
    "- Configure `pxt serve` in pyproject.toml under [tool.pixeltable.serve]:\n"
    "  - Set the query route: query = \"schema:analyze_review\"\n"
    "- Write a schema.py that defines the table and the query function\n"
    "- The API should be startable with: `python schema.py && pxt serve pipeline`"
)


class U3PxtServeVerifier(StoryVerifier):

    @property
    def story_id(self) -> str:
        return "u3_pxt_serve"

    @property
    def positive_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"import pixeltable|from pixeltable", "uses pixeltable"),
            (r"@pxt\.query\b", "defines @pxt.query function"),
            (r"add_computed_column\s*\(", "uses computed columns"),
            (r"\[tool\.pixeltable\.serve\]", "configures [tool.pixeltable.serve]"),
            (r"query\s*=\s*['\"].*:.*['\"]", "uses colon notation for query route"),
            (r"pxt\s+serve", "runs pxt serve"),
            (r"chat_completions|messages", "calls an LLM"),
            (r"if_exists\s*=\s*['\"]ignore['\"]", "uses if_exists='ignore'"),
        ]

    @property
    def negative_patterns(self) -> list[tuple[str, str]]:
        return [
            (r"from flask\s+import|from django", "uses Flask/Django instead of pxt serve"),
            (r"from fastapi\s+import\s+FastAPI", "manually creates FastAPI app"),
            (r"app\s*=\s*FastAPI\s*\(", "manually instantiates FastAPI"),
            (r"query\s*=\s*['\"][\w]+\.[\w]+['\"]", "uses dot notation for query route"),
            (r"from langchain", "imports LangChain"),
            (r"import pandas|from pandas", "uses pandas as working store"),
            (r"modules\s*=\s*\[", "uses deprecated 'modules' field"),
        ]

    def functional_check(self, sandbox: PixeltableSandbox) -> dict:
        tables = sandbox.list_tables()

        if not tables:
            return {"pass": False, "reason": "no tables created"}

        has_reviews = any("review" in t.lower() for t in tables)
        if not has_reviews:
            return {
                "pass": False,
                "reason": f"expected reviews table, found: {tables}",
            }

        review_table = next(t for t in tables if "review" in t.lower())

        check_code = f"""\
import pixeltable as pxt
import json

try:
    t = pxt.get_table('{review_table}')
    cols = [c.name for c in t.columns()]
    has_sentiment = any('sentiment' in c.lower() for c in cols)
    has_summary = any('summary' in c.lower() or 'summar' in c.lower() for c in cols)
    print(json.dumps({{
        "columns": cols,
        "has_sentiment": has_sentiment,
        "has_summary": has_summary,
    }}))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
"""
        result = sandbox.exec_verification(check_code)

        if not result.success:
            return {"pass": False, "reason": f"verification failed: {result.stderr}"}

        try:
            data = json.loads(result.stdout.strip())
        except (json.JSONDecodeError, ValueError):
            return {"pass": False, "reason": f"bad output: {result.stdout}"}

        if "error" in data:
            return {"pass": False, "reason": data["error"]}

        if not data.get("has_sentiment"):
            return {"pass": False, "reason": "missing sentiment computed column"}
        if not data.get("has_summary"):
            return {"pass": False, "reason": "missing summary computed column"}

        return {
            "pass": True,
            "columns": data.get("columns", []),
            "tables_found": tables,
        }
