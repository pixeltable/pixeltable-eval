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

from eval.runners.base import BaseRunner, RunnerResult, collect_created_files


class ClaudeCodeRunner(BaseRunner):

    def __init__(self, model: str | None = "sonnet", max_turns: int = 25):
        # Default "sonnet": an alias the CLI resolves to its latest sonnet,
        # so the cohort moves with releases instead of hard-failing like a
        # dated pin did. Pass --model for a specific dated id or another
        # family; None defers to the CLI default.
        self.model = model
        self.max_turns = max_turns

    @property
    def name(self) -> str:
        return "claude_code"

    def run(self, prompt: str, workdir: Path, timeout: int = 600) -> RunnerResult:
        cmd = [
            "claude",
            "--print",
            "--output-format", "json",
            "--max-turns", str(self.max_turns),
            "--allowedTools", "Read,Write,Edit,Bash,WebSearch,WebFetch",
            "--dangerously-skip-permissions",
        ]
        if self.model:
            cmd += ["--model", self.model]
        cmd += ["-p", prompt]

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
            files_created = collect_created_files(workdir)
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

        # --output-format json wraps the result in an envelope carrying
        # usage and cost; fall back to treating stdout as plain text if the
        # envelope shape ever changes.
        envelope = None
        try:
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, dict):
                envelope = parsed
        except json.JSONDecodeError:
            pass

        raw = envelope.get("result", "") if envelope else proc.stdout
        if not isinstance(raw, str):
            raw = proc.stdout
        usage = envelope.get("usage") or {} if envelope else {}
        files_created = collect_created_files(workdir)
        code = self._extract_code(raw, files_created)

        error = proc.stderr[:500] if proc.returncode != 0 else None
        if envelope and envelope.get("is_error"):
            error = error or str(envelope.get("result", ""))[:500]

        return RunnerResult(
            runner_name=self.name,
            raw_output=raw,
            extracted_code=code,
            files_created=files_created,
            turns=max(1, int(envelope.get("num_turns", 1))) if envelope else self._count_turns(raw),
            tokens_in=int(usage.get("input_tokens", 0)) + int(usage.get("cache_read_input_tokens", 0)),
            tokens_out=int(usage.get("output_tokens", 0)),
            cost_usd=float(envelope.get("total_cost_usd", 0.0)) if envelope else 0.0,
            elapsed_seconds=elapsed,
            error=error,
        )

    def _build_env(self, workdir: Path) -> dict:
        env = os.environ.copy()
        env["PIXELTABLE_HOME"] = str(workdir / ".pixeltable_eval")
        env.pop("VIRTUAL_ENV", None)
        return env

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
