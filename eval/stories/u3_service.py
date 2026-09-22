"""
U3: Serving a pipeline with pxt service

Prompt: "Build a Pixeltable-powered REST API for movie review analysis."

Verifier checks:
- Static: uses TableModel, FastAPIRouter routes, computed columns,
  pxt schema update + pxt service update
- Negative: no retired pxt serve CLI / TOML routes, no hand-rolled server,
  no notebook APIs in app code
- Functional: `pxt init` + `pxt schema update` materializes a reviews table
  with sentiment and summary computed columns, then `pxt service update`
  starts the service and POST /analyze is exercised; services are stopped
  afterward
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
            (r"insert_route\s*\(", "declares an insert route"),
            (r"path\s*=\s*['\"]/analyze['\"]", "exposes the /analyze endpoint"),
            (r"chat_completions|messages", "calls an LLM"),
            (r"\.choices\[0\]\.message\.content", "extracts OpenAI response correctly"),
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
import time
import urllib.error
import urllib.request
from pathlib import Path


# Use the pxt binary from the same interpreter as this script; a different
# pxt on PATH may run a different pixeltable version.
def sh(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def first_json(stdout):
    # pxt may print a connection banner before the payload; decode the first
    # JSON value found in the output.
    dec = json.JSONDecoder()
    for i, ch in enumerate(stdout):
        if ch in "[{":
            try:
                return dec.raw_decode(stdout[i:])[0]
            except json.JSONDecodeError:
                continue
    return None


out = {"columns": [], "has_sentiment": False, "has_summary": False, "served": False}
pxtc = "pxt"
try:
    exe_pxt = Path(sys.executable).parent / "pxt"
    if exe_pxt.exists():
        pxtc = str(exe_pxt)
    sh([pxtc, "init"], timeout=60)
    upd = sh([pxtc, "schema", "update", "app.py", "eval_app", "-f"])
    if upd.returncode != 0:
        out["error"] = f"pxt schema update failed: {upd.stderr[-300:]}"
        print(json.dumps(out))
        sys.exit(0)

    import pixeltable as pxt
    tables = pxt.list_tables()
    review_tables = [t for t in tables if t.startswith("eval_app.") and "review" in t.lower()]
    if not review_tables:
        review_tables = [t for t in tables if "review" in t.lower()]
    if not review_tables:
        out["error"] = f"no reviews table, found: {tables}"
        print(json.dumps(out))
        sys.exit(0)

    t = pxt.get_table(review_tables[0])
    cols = t.get_metadata()["columns"]
    out["columns"] = list(cols)
    out["has_sentiment"] = any(
        "sentiment" in name.lower() and meta.get("is_computed")
        for name, meta in cols.items()
    )
    out["has_summary"] = any(
        "summar" in name.lower() and meta.get("is_computed")
        for name, meta in cols.items()
    )
    if not (out["has_sentiment"] and out["has_summary"]):
        print(json.dumps(out))
        sys.exit(0)

    # Serving layer: the story's point is a running API, not just a schema.
    chk = sh([pxtc, "service", "check", "app.py"], timeout=60)
    out["service_check_ok"] = chk.returncode == 0

    svc = sh([pxtc, "service", "update", "app.py", "eval_app", "-f"], timeout=180)
    out["service_update_rc"] = svc.returncode
    if svc.returncode != 0:
        out["service_update_err"] = (svc.stderr or svc.stdout)[-300:]
    else:
        services = []
        deadline = time.time() + 90
        while time.time() < deadline:
            lst = sh([pxtc, "service", "list", "eval_app", "--json"], timeout=30)
            services = first_json(lst.stdout) or []
            if any(s.get("state") == "AVAILABLE" and s.get("port") for s in services):
                break
            if services and all(s.get("state") == "FAILED" for s in services):
                break
            time.sleep(3)
        out["services"] = [
            {
                "name": s.get("name"),
                "port": s.get("port"),
                "state": s.get("state"),
                "routes": [
                    f"{r.get('method')} {r.get('path')}"
                    for r in s.get("spec", {}).get("routes", [])
                ],
            }
            for s in services
        ]
        target = None
        for s in services:
            if s.get("state") != "AVAILABLE" or not s.get("port"):
                continue
            for r in s.get("spec", {}).get("routes", []):
                if r.get("method") == "POST" and r.get("path", "").rstrip("/").endswith("/analyze"):
                    target = (s, r)
                    break
            if target:
                break
        out["served"] = target is not None
        if target:
            inst, route = target
            # POST once to prove the route is live. Inputs are filled from
            # the route's own declaration; provider auth failures are
            # recorded, not treated as app defects.
            body = {name: "An absolute delight of a film." for name in route.get("inputs") or []}
            body = body or {"title": "ok", "review_text": "An absolute delight of a film."}
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{inst['port']}{route['path']}",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    out["post_status"] = resp.status
                    out["post_body"] = resp.read(400).decode(errors="replace")[:300]
            except urllib.error.HTTPError as e:
                out["post_status"] = e.code
                out["post_body"] = e.read(300).decode(errors="replace")
            except Exception as e:
                out["post_error"] = str(e)[:200]
except FileNotFoundError:
    out["error"] = "pxt CLI not on PATH"
except Exception as e:
    out["error"] = str(e)[:300]
finally:
    # Leave nothing running: stop the services bound to this sandbox's
    # catalog, then the daemon spawned on this run's private PXT_PORT.
    try:
        running = first_json(sh([pxtc, "service", "list", "eval_app", "--json"], timeout=30).stdout) or []
        names = [f"eval_app/{s['name']}" for s in running if s.get("name")]
        if names:
            sh([pxtc, "service", "stop", *names], timeout=60)
    except Exception:
        pass
    try:
        sh([pxtc, "daemon", "stop"], timeout=30)
    except Exception:
        pass

print(json.dumps(out))
"""
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

        if not data.get("has_sentiment"):
            return {"pass": False, "reason": "missing sentiment computed column"}
        if not data.get("has_summary"):
            return {"pass": False, "reason": "missing summary computed column"}
        if data.get("service_update_rc") not in (None, 0):
            return {
                "pass": False,
                "reason": f"pxt service update failed: {data.get('service_update_err', '?')}",
                "services": data.get("services", []),
            }
        if not data.get("served"):
            return {
                "pass": False,
                "reason": "no running service exposes POST /analyze",
                "services": data.get("services", []),
            }

        return {
            "pass": True,
            "columns": data.get("columns", []),
            "services": data.get("services", []),
            "service_check_ok": data.get("service_check_ok"),
            "post_status": data.get("post_status"),
            "post_body": data.get("post_body"),
        }
