"""
Grader for pxt_service eval.

Checks that the agent declares the pipeline as a TableModel with
FastAPIRouter routes and starts it with the pxt CLI, instead of reaching
for the retired pxt serve CLI / TOML routes or a hand-rolled server.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"TableModel|model_base\s*\(", "defines a TableModel"),
    (r"FastAPIRouter|from pixeltable\.serving", "uses FastAPIRouter"),
    (r"add_insert_route|add_compute_route|insert_route\s*\(", "declares an insert/compute route"),
    (r"chat_completions|messages", "calls an LLM"),
    (r"\.choices\[0\]\.message\.content", "extracts OpenAI response correctly"),
    (r"pxt\s+schema\s+update", "applies schema with pxt schema update"),
    (r"pxt\s+service\s+update", "starts service with pxt service update"),
]

NEGATIVE_PATTERNS = [
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
