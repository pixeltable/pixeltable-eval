"""
U4: CRUD service over a TableModel (dependent instructions)

Prompt pattern adapted from prompt-bank "phase-ordered" task styles: each
requirement builds on the artifact of the previous one (model -> computed
column -> insert route -> query route filtering on what insert stored ->
delete route removing what query found).

Verifier checks:
- Static: TableModel, @pxt.udf computed slug, FastAPIRouter with insert /
  query / delete routes, pxt schema update + pxt service update
- Negative: retired pxt serve / TOML routes, notebook APIs in app code,
  hand-rolled server, LangChain / vector DBs / pandas-as-store
- Functional: schema update materializes 'products' with a computed slug,
  the service boots, POST /products stores a row, GET /product returns it,
  and the delete route removes it (when its inputs are satisfiable). No
  provider keys needed: the computed column is a pure-Python UDF.
"""

from __future__ import annotations

import json

from eval.sandbox import PixeltableSandbox
from eval.stories._service_check import SERVICE_CHECK_PREAMBLE
from eval.verifier import StoryVerifier


PROMPT = (
    "Build a Pixeltable-powered REST API that manages a product catalog.\n\n"
    "Requirements (each step builds on the previous):\n"
    "- Write app.py using TableModel (pxt.model_base()): a table 'products' "
    "with columns sku (pxt.String), name (pxt.String), price (pxt.Float)\n"
    "- Add a computed column 'slug' on that model, derived from name via a "
    "@pxt.udf (lowercase, spaces replaced with hyphens)\n"
    "- With a FastAPIRouter (from pixeltable.serving), expose on the products "
    "table, in this order:\n"
    "  1. an insert route at POST /products taking sku, name, price and "
    "returning sku and slug\n"
    "  2. a query route at GET /product that takes a sku and returns the "
    "matching row's name, price, and slug\n"
    "  3. a delete route at POST /products/delete that removes the row the "
    "query route returned\n"
    "- Give me the commands to create the tables and start the service with "
    "the pxt CLI"
)


class U4CrudServiceVerifier(StoryVerifier):

    @property
    def story_id(self) -> str:
        return "u4_crud_service"

    @property
    def positive_patterns(self) -> list[tuple[str, str]]:
        return [
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
            (r"sqlite3|psycopg2", "hand-rolls SQL storage instead of a table"),
            (r"modules\s*=\s*\[", "writes a TOML modules list (retired field)"),
        ]

    def functional_check(self, sandbox: PixeltableSandbox) -> dict:
        # exec_verification overwrites _eval_script.py, so preserve the
        # generated code as app.py for pxt schema update (same as u3).
        script = sandbox.workdir / "_eval_script.py"
        if not script.exists():
            return {"pass": False, "reason": "no generated file to apply"}
        (sandbox.workdir / "app.py").write_text(script.read_text())

        check_code = SERVICE_CHECK_PREAMBLE + '''\

out = {
    "columns": [], "has_slug": False, "served": False,
    "insert_status": None, "query_status": None,
    "delete_route": False, "delete_verified": None,
}
pxtc = pxt_bin()

SEED = {"sku": "SKU-1", "name": "Test Widget", "price": 9.99}

def fill_inputs(route, row):
    """Fill declared route inputs from a known row; fall back to the seed
    values by input-name heuristic."""
    body = {}
    for name in route.get("inputs") or []:
        lname = str(name).lower()
        if row and name in row:
            body[name] = row[name]
        elif "sku" in lname:
            body[name] = SEED["sku"]
        elif "price" in lname or "amount" in lname:
            body[name] = SEED["price"]
        elif "name" in lname or "title" in lname:
            body[name] = SEED["name"]
        else:
            body[name] = "x"
    return body or dict(SEED)


def find_row(obj):
    """Recursively find the first dict that carries a sku-like field."""
    if isinstance(obj, dict):
        if any("sku" in str(k).lower() for k in obj):
            return obj
        for v in obj.values():
            found = find_row(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_row(v)
            if found:
                return found
    return None


def sku_of(row):
    """Value of a row's sku-ish field, or None."""
    if isinstance(row, dict):
        for k, v in row.items():
            if "sku" in str(k).lower():
                return v
    return None


try:
    sh([pxtc, "init"], timeout=60)
    upd = sh([pxtc, "schema", "update", "app.py", "eval_app", "-f"])
    if upd.returncode != 0:
        out["error"] = f"pxt schema update failed: {upd.stderr[-300:]}"
        print(json.dumps(out))
        sys.exit(0)

    import pixeltable as pxt
    tables = pxt.list_tables()
    prod = [t for t in tables if t.startswith("eval_app.") and "product" in t.lower()]
    if not prod:
        prod = [t for t in tables if "product" in t.lower()]
    if not prod:
        out["error"] = f"no products table, found: {tables}"
        print(json.dumps(out))
        sys.exit(0)

    t = pxt.get_table(prod[0])
    cols = t.get_metadata()["columns"]
    out["columns"] = list(cols)
    out["has_slug"] = any(
        "slug" in name.lower() and meta.get("is_computed")
        for name, meta in cols.items()
    )
    if not out["has_slug"]:
        print(json.dumps(out))
        sys.exit(0)

    svc = sh([pxtc, "service", "update", "app.py", "eval_app", "-f"], timeout=180)
    out["service_update_rc"] = svc.returncode
    if svc.returncode != 0:
        out["service_update_err"] = (svc.stderr or svc.stdout)[-300:]
    else:
        services = wait_available(pxtc, "eval_app")
        out["services"] = service_summary(services)
        out["served"] = any(
            s.get("state") == "AVAILABLE" for s in services
        )

        # 1. insert route stores the row
        target = find_route(services, "POST", "/products")
        row = None
        if target:
            inst, route = target
            status, text, err = post_json(inst["port"], route["path"], fill_inputs(route, None))
            out["insert_status"] = status
            out["insert_body"] = (text or err or "")[:300]
            if text:
                try:
                    row = find_row(json.loads(text))
                except json.JSONDecodeError:
                    row = None
        row = row or dict(SEED)

        # 2. query route returns the stored row, verified by sku value
        qtarget = find_route(services, "GET", "/product")
        if not qtarget:
            qtarget = find_route(services, "POST", "/product")
        out["query_sku_ok"] = None
        if qtarget:
            inst, route = qtarget
            params = fill_inputs(route, row)
            if route.get("method") == "GET":
                status, text, err = get_json(inst["port"], route["path"], params)
            else:
                status, text, err = post_json(inst["port"], route["path"], params)
            out["query_status"] = status
            out["query_body"] = (text or err or "")[:300]
            if text and status == 200:
                try:
                    fresher = find_row(json.loads(text))
                except Exception:
                    fresher = None
                out["query_sku_ok"] = (
                    fresher is not None and sku_of(fresher) == SEED["sku"]
                )
                if fresher:
                    row.update(fresher)
            else:
                out["query_sku_ok"] = False

        # 3. delete route removes it: a 2xx alone is not proof; the row must
        # be gone when the query route is asked again.
        dtarget = find_route(services, "POST", "delete")
        out["delete_route"] = dtarget is not None
        if dtarget:
            inst, route = dtarget
            declared = [str(n) for n in (route.get("inputs") or [])]
            if declared:
                body = fill_inputs(route, row)
                satisfiable = all(n in row or "sku" in n.lower() for n in declared)
            else:
                # Undeclared inputs: offer the likely row keys (pk or sku).
                body = {k: row[k] for k in ("id", "sku") if k in row}
                satisfiable = bool(body)
            if satisfiable:
                status, text, err = post_json(inst["port"], route["path"], body)
                out["delete_status"] = status
                out["delete_body"] = (text or err or "")[:300]
                if not (status and 200 <= status < 300):
                    out["delete_verified"] = False
                elif qtarget:
                    inst2, route2 = qtarget
                    params = fill_inputs(route2, row)
                    if route2.get("method") == "GET":
                        s2, t2, e2 = get_json(inst2["port"], route2["path"], params)
                    else:
                        s2, t2, e2 = post_json(inst2["port"], route2["path"], params)
                    out["post_delete_query_status"] = s2
                    gone = True
                    if s2 and 200 <= s2 < 300 and t2:
                        try:
                            leftover = find_row(json.loads(t2))
                        except Exception:
                            leftover = None
                        if leftover is not None and sku_of(leftover) == SEED["sku"]:
                            gone = False
                    out["delete_verified"] = gone
                else:
                    out["delete_verified"] = None
                    out["delete_unverifiable"] = True
            else:
                out["delete_verified"] = None
                out["delete_unsatisfiable_inputs"] = declared
except FileNotFoundError:
    out["error"] = "pxt CLI not on PATH"
except Exception as e:
    out["error"] = str(e)[:300]
finally:
    cleanup_services(pxtc, "eval_app")

print(json.dumps(out))
'''

        result = sandbox.exec_verification(check_code)

        if not result.success:
            return {"pass": False, "reason": f"verification failed: {result.stderr}"}

        try:
            # pxt prints a connection banner to stdout; the JSON payload is
            # always the last line.
            data = json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, ValueError, IndexError):
            return {"pass": False, "reason": f"bad output: {result.stdout}"}

        if "error" in data:
            if "pxt CLI not on PATH" in data["error"]:
                return {"pass": None, "skipped": True, "reason": data["error"]}
            return {"pass": False, "reason": data["error"]}

        if not data.get("has_slug"):
            return {"pass": False, "reason": "missing computed slug column"}
        if data.get("service_update_rc") not in (None, 0):
            return {
                "pass": False,
                "reason": f"pxt service update failed: {data.get('service_update_err', '?')}",
                "services": data.get("services", []),
            }
        if not data.get("served"):
            return {
                "pass": False,
                "reason": "no AVAILABLE service",
                "services": data.get("services", []),
            }
        if not (data.get("insert_status") and 200 <= data["insert_status"] < 300):
            return {
                "pass": False,
                "reason": f"POST /products did not store a row: {data.get('insert_body', '?')}",
                "insert_status": data.get("insert_status"),
            }
        if not (data.get("query_status") and 200 <= data["query_status"] < 300):
            return {
                "pass": False,
                "reason": f"query route did not return the row: {data.get('query_body', '?')}",
                "query_status": data.get("query_status"),
            }
        if data.get("query_sku_ok") is not True:
            return {
                "pass": False,
                "reason": "query route response does not contain the inserted sku",
                "query_body": data.get("query_body"),
            }
        if not data.get("delete_route"):
            return {
                "pass": False,
                "reason": "no delete route registered",
                "services": data.get("services", []),
            }
        if data.get("delete_verified") is not True:
            detail = (
                f"row still present after delete: {data.get('delete_body', '?')}"
                if data.get("delete_verified") is False
                else f"delete could not be exercised or verified "
                     f"(inputs: {data.get('delete_unsatisfiable_inputs', '?')})"
            )
            return {
                "pass": False,
                "reason": detail,
                "delete_status": data.get("delete_status"),
            }

        return {
            "pass": True,
            "columns": data.get("columns", []),
            "services": data.get("services", []),
            "insert_status": data.get("insert_status"),
            "query_status": data.get("query_status"),
            "delete_verified": data.get("delete_verified"),
            "post_delete_query_status": data.get("post_delete_query_status"),
        }
