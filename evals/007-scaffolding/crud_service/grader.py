"""
Grader for crud_service eval.

Mirrors the u4_crud_service story patterns: TableModel + UDF computed
column + insert/query/delete routes driven by the pxt CLI.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"TableModel|model_base\s*\(", "defines a TableModel"),
    (r"@pxt\.udf\b", "defines a UDF for the computed slug"),
    (r"slug", "declares the slug computed column"),
    (r"FastAPIRouter|from pixeltable\.serving", "uses FastAPIRouter"),
    (r"add_insert_route|insert_route\s*\(", "declares an insert route"),
    (r"['\"]/products?['\"]", "exposes the /products path"),
    (r"add_query_route|query_route\s*\(|@pxt\.query\b", "declares a query route"),
    (r"add_delete_route|delete_route\s*\(", "declares a delete route"),
    (r"pxt\s+schema\s+update", "applies schema with pxt schema update"),
    (r"pxt\s+service\s+(update|run)\b", "starts the service with pxt service update/run"),
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
    (r"sqlite3|psycopg2", "hand-rolls SQL storage instead of a table"),
    (r"modules\s*=\s*\[", "writes a TOML modules list (retired field)"),
]
