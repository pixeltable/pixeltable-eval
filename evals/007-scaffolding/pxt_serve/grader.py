"""
Grader for pxt_serve eval.

Checks that the agent correctly configures pxt serve with
pyproject.toml and a proper schema module.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"@pxt\.query\b", "defines @pxt.query function"),
    (r"add_computed_column\s*\(", "uses computed columns"),
    (r"\[tool\.pixeltable\.serve\]", "configures [tool.pixeltable.serve]"),
    (r"query\s*=\s*['\"].*:.*['\"]", "uses colon notation for query route"),
    (r"pxt\s+serve", "runs pxt serve"),
    (r"chat_completions|messages", "calls an LLM"),
    (r"if_exists\s*=\s*['\"]ignore['\"]", "uses if_exists='ignore'"),
]

NEGATIVE_PATTERNS = [
    (r"from flask\s+import|from django", "uses Flask/Django instead of pxt serve"),
    (r"from fastapi\s+import\s+FastAPI", "manually creates FastAPI app instead of pxt serve"),
    (r"app\s*=\s*FastAPI\s*\(", "manually instantiates FastAPI (pxt serve handles this)"),
    (r"query\s*=\s*['\"].*\..*['\"]", "uses dot notation for query route (should use colon)"),
    (r"from langchain", "imports LangChain"),
    (r"import pandas|from pandas", "uses pandas as working store"),
    (r"modules\s*=\s*\[", "uses deprecated 'modules' field in pyproject.toml"),
]
