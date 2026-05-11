"""
Isolated Pixeltable execution environment for eval runs.

Creates a fresh PIXELTABLE_HOME per run so state never leaks between cells.
Executes generated code in a subprocess with timeout, captures stdout/stderr,
and provides access to the resulting table state for functional verification.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    generated_files: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class PixeltableSandbox:
    """Fresh Pixeltable environment scoped to a single eval run."""

    def __init__(self, fixture_dir: Path | str | None = None, timeout: int = 300):
        self.home = Path(tempfile.mkdtemp(prefix="pxteval_"))
        self.workdir = Path(tempfile.mkdtemp(prefix="pxtwork_"))
        self.fixture_dir = Path(fixture_dir) if fixture_dir else None
        self.timeout = timeout

        if self.fixture_dir and self.fixture_dir.exists():
            docs_dir = self.workdir / "docs"
            docs_dir.mkdir(exist_ok=True)
            for f in self.fixture_dir.iterdir():
                if f.is_file():
                    shutil.copy2(f, docs_dir / f.name)

    def exec_code(self, code: str) -> SandboxResult:
        """Execute a Python code string in an isolated subprocess."""
        script = self.workdir / "_eval_script.py"
        script.write_text(code)

        env = os.environ.copy()
        env["PIXELTABLE_HOME"] = str(self.home)
        env.pop("PIXELTABLE_CONFIG", None)

        import time
        start = time.monotonic()

        try:
            proc = subprocess.run(
                ["python3", str(script)],
                cwd=str(self.workdir),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            elapsed = time.monotonic() - start

            generated = [
                str(p.relative_to(self.workdir))
                for p in self.workdir.rglob("*.py")
                if p.name != "_eval_script.py"
            ]

            return SandboxResult(
                success=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                generated_files=generated,
                elapsed_seconds=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Timeout after {self.timeout}s",
                exit_code=-1,
                elapsed_seconds=elapsed,
            )

    def exec_verification(self, code: str) -> SandboxResult:
        """Execute verification code that imports pixeltable and inspects tables.

        Runs in the same PIXELTABLE_HOME as the generated code so it can
        access tables created during the eval run.
        """
        return self.exec_code(code)

    def query_table(self, table_path: str, select_expr: str = "*", limit: int = 10) -> str:
        """Quick helper to query a table in the sandbox's Pixeltable instance."""
        verification = textwrap.dedent(f"""\
            import pixeltable as pxt
            import json

            try:
                t = pxt.get_table('{table_path}')
                if '{select_expr}' == '*':
                    rows = t.limit({limit}).collect()
                else:
                    rows = t.select({select_expr}).limit({limit}).collect()
                print(json.dumps({{"row_count": t.count(), "sample": str(rows)}}))
            except Exception as e:
                print(json.dumps({{"error": str(e)}}))
        """)
        result = self.exec_verification(verification)
        return result.stdout.strip() if result.success else result.stderr

    def list_tables(self) -> list[str]:
        """List all tables in the sandbox Pixeltable instance."""
        code = textwrap.dedent("""\
            import pixeltable as pxt
            import json
            tables = pxt.list_tables()
            print(json.dumps([str(t) for t in tables]))
        """)
        result = self.exec_verification(code)
        if result.success and result.stdout.strip():
            try:
                return json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                return []
        return []

    def cleanup(self):
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.workdir, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()
