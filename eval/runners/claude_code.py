"""
Claude Code runner using --print (headless) mode.

Drives the real Claude Code agent runtime: tool use (file read/write, shell,
web search), self-correction, AGENTS.md/skill loading — everything except the
interactive UI.

Requires: `claude` CLI installed and ANTHROPIC_API_KEY set.
"""

from __future__ import annotations

import json
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

    def run(self, prompt: str, workdir: Path, timeout: int = 300) -> RunnerResult:
        cmd = [
            "claude",
            "--print",
            "--output-format", "json",
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
            return RunnerResult(
                runner_name=self.name,
                raw_output="",
                extracted_code="",
                error=f"Timeout after {timeout}s",
                elapsed_seconds=time.monotonic() - start,
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

        tokens_in, tokens_out, turns = 0, 0, 0
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                tokens_in = data.get("usage", {}).get("input_tokens", 0)
                tokens_out = data.get("usage", {}).get("output_tokens", 0)
                turns = data.get("num_turns", 1)
        except (json.JSONDecodeError, TypeError):
            pass

        return RunnerResult(
            runner_name=self.name,
            raw_output=raw,
            extracted_code=code,
            files_created=files_created,
            turns=turns,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            elapsed_seconds=elapsed,
            error=proc.stderr if proc.returncode != 0 else None,
        )

    def _build_env(self, workdir: Path) -> dict:
        import os
        env = os.environ.copy()
        env["PIXELTABLE_HOME"] = str(workdir / ".pixeltable_eval")
        return env

    def _collect_files(self, workdir: Path) -> dict[str, str]:
        files = {}
        for py_file in workdir.rglob("*.py"):
            rel = str(py_file.relative_to(workdir))
            if not rel.startswith("."):
                try:
                    files[rel] = py_file.read_text()
                except Exception:
                    pass
        return files

    def _extract_code(self, raw_output: str, files: dict[str, str]) -> str:
        if files:
            main_candidates = ["app.py", "main.py", "rag.py", "pipeline.py"]
            for candidate in main_candidates:
                if candidate in files:
                    return files[candidate]
            return "\n\n".join(files.values())

        return self.extract_python_from_output(raw_output)
