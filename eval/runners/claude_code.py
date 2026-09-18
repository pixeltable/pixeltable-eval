"""
Claude Code runner using --print (headless) mode.

Drives the real Claude Code agent runtime: tool use (file read/write, shell,
web search), self-correction, AGENTS.md/skill loading — everything except the
interactive UI.

Requires: `claude` CLI installed and ANTHROPIC_API_KEY set.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from eval.runners.base import BaseRunner, RunnerResult


class ClaudeCodeRunner(BaseRunner):

    def __init__(self, model: str = "claude-sonnet-4-20250514", max_turns: int = 25):
        self.model = model
        self.max_turns = max_turns

    @property
    def name(self) -> str:
        return "claude_code"

    def run(self, prompt: str, workdir: Path, timeout: int = 600) -> RunnerResult:
        cmd = [
            "claude",
            "--print",
            "--output-format", "text",
            "--model", self.model,
            "--max-turns", str(self.max_turns),
            "--allowedTools", "Read,Write,Edit,Bash,WebSearch,WebFetch",
            "--dangerously-skip-permissions",
            "-p", prompt,
        ]

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._build_env(workdir),
            )
            elapsed = time.monotonic() - start
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            files_created = self._collect_files(workdir)
            code = self._extract_code("", files_created)
            return RunnerResult(
                runner_name=self.name,
                raw_output="",
                extracted_code=code,
                files_created=files_created,
                error=f"Timeout after {timeout}s (files may still be valid)",
                elapsed_seconds=elapsed,
            )
        except FileNotFoundError:
            return RunnerResult(
                runner_name=self.name,
                raw_output="",
                extracted_code="",
                error="claude CLI not found. Install: npm install -g @anthropic-ai/claude-code",
                elapsed_seconds=0,
            )

        raw = proc.stdout
        files_created = self._collect_files(workdir)
        code = self._extract_code(raw, files_created)

        return RunnerResult(
            runner_name=self.name,
            raw_output=raw,
            extracted_code=code,
            files_created=files_created,
            turns=self._count_turns(raw),
            elapsed_seconds=elapsed,
            error=proc.stderr[:500] if proc.returncode != 0 else None,
        )

    def _build_env(self, workdir: Path) -> dict:
        env = os.environ.copy()
        env["PIXELTABLE_HOME"] = str(workdir / ".pixeltable_eval")
        env.pop("VIRTUAL_ENV", None)
        return env

    def _collect_files(self, workdir: Path) -> dict[str, str]:
        files = {}
        skip_prefixes = (".", "_", "node_modules")
        collect_exts = {".py", ".toml", ".md", ".txt", ".sh"}
        for f in workdir.rglob("*"):
            rel = str(f.relative_to(workdir))
            if not f.is_file() or f.suffix not in collect_exts:
                continue
            if any(rel.startswith(p) for p in skip_prefixes):
                continue
            if "venv" in rel or "site-packages" in rel:
                continue
            try:
                content = f.read_text()
                if content.strip():
                    files[rel] = content
            except Exception:
                pass
        return files

    def _extract_code(self, raw_output: str, files: dict[str, str]) -> str:
        # Only Python counts as extracted code: it is executed by the sandbox
        # and concatenating TOML/shell/markdown would corrupt it. Other files
        # still reach the verifier via files_created -> extra_evidence.
        py_files = {name: c for name, c in files.items() if name.endswith(".py")}
        if py_files:
            main_candidates = [
                "app.py", "main.py", "rag.py", "pipeline.py",
                "pdf_qa_app.py", "pdf_rag_app.py", "pdf_rag.py",
            ]
            for candidate in main_candidates:
                if candidate in py_files:
                    return py_files[candidate]
            return "\n\n".join(py_files.values())

        return self._extract_python_from_text(raw_output)

    def _extract_python_from_text(self, text: str) -> str:
        if not text:
            return ""

        # Try to parse as JSON envelope (in case --output-format json was used)
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                text = data.get("result", data.get("text", data.get("content", "")))
                if isinstance(text, list):
                    text = "\n".join(
                        block.get("text", "") for block in text
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
        except (json.JSONDecodeError, TypeError):
            pass

        # Extract Python code blocks
        blocks = re.findall(r"```python\s*\n(.*?)```", text, re.DOTALL)
        if blocks:
            return "\n\n".join(blocks)

        blocks = re.findall(r"```\s*\n(.*?)```", text, re.DOTALL)
        python_blocks = [b for b in blocks if "import " in b or "def " in b or "pxt." in b]
        if python_blocks:
            return "\n\n".join(python_blocks)

        return ""

    def _count_turns(self, raw: str) -> int:
        # Rough heuristic from text output
        tool_markers = raw.count("⏺") if "⏺" in raw else 0
        return max(1, tool_markers)
