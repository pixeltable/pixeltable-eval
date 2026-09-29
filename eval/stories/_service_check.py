"""
Shared preamble for story functional checks that exercise `pxt service`.

The check code runs as a standalone script inside the sandbox subprocess,
so helpers ship as source text prepended to each story's check_code rather
than as imports.
"""

SERVICE_CHECK_PREAMBLE = '''\
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


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


def pxt_bin():
    # Use the pxt binary from the same interpreter as this script; a different
    # pxt on PATH may run a different pixeltable version.
    exe = Path(sys.executable).parent / "pxt"
    return str(exe) if exe.exists() else "pxt"


def wait_available(pxtc, target, timeout_s=90):
    """Poll `pxt service list <target> --json` until some service is
    AVAILABLE with a port, all are FAILED, or the deadline hits."""
    services = []
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        lst = sh([pxtc, "service", "list", target, "--json"], timeout=30)
        services = first_json(lst.stdout) or []
        if any(s.get("state") == "AVAILABLE" and s.get("port") for s in services):
            break
        if services and all(s.get("state") == "FAILED" for s in services):
            break
        time.sleep(3)
    return services


def service_summary(services):
    return [
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


def find_route(services, method, suffix):
    """Locate (service_instance, route) for a method + path suffix across
    AVAILABLE services. Routes are read from the service spec."""
    for s in services:
        if s.get("state") != "AVAILABLE" or not s.get("port"):
            continue
        for r in s.get("spec", {}).get("routes", []):
            if r.get("method") == method and r.get("path", "").rstrip("/").endswith(suffix):
                return s, r
    return None


def post_json(port, path, body, timeout=90):
    """POST a JSON body. Returns (status, body_text, error) — exactly one of
    body_text/error is set for non-2xx paths."""
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(400).decode(errors="replace"), None
    except urllib.error.HTTPError as e:
        return e.code, e.read(300).decode(errors="replace"), None
    except Exception as e:
        return None, None, str(e)[:200]


def get_json(port, path, params=None, timeout=60):
    """GET with optional query params. Same return shape as post_json."""
    url = f"http://127.0.0.1:{port}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read(400).decode(errors="replace"), None
    except urllib.error.HTTPError as e:
        return e.code, e.read(300).decode(errors="replace"), None
    except Exception as e:
        return None, None, str(e)[:200]


def cleanup_services(pxtc, target):
    """Leave nothing running: stop services bound to this sandbox's
    catalog target, then the daemon on this run's private PXT_PORT."""
    try:
        running = first_json(sh([pxtc, "service", "list", target, "--json"], timeout=30).stdout) or []
        names = [f"{target}/{s['name']}" for s in running if s.get("name")]
        if names:
            sh([pxtc, "service", "stop", *names], timeout=60)
    except Exception:
        pass
    try:
        sh([pxtc, "daemon", "stop"], timeout=30)
    except Exception:
        pass
'''
