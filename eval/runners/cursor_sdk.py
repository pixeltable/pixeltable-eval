"""
Cursor SDK runner using @cursor/sdk (TypeScript).

Drives the real Cursor agent runtime programmatically: codebase indexing,
MCP, subagent spawning, file read/write, shell execution.

Requires: Node.js 18+, @cursor/sdk installed, CURSOR_API_KEY set.

Since the SDK is TypeScript, this runner shells out to a small Node script
that creates an agent, runs the prompt, and returns results as JSON.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from eval.runners.base import BaseRunner, RunnerResult, collect_created_files

CURSOR_RUNNER_SCRIPT = """\
const { Agent } = require("@cursor/sdk");

async function main() {
  const prompt = process.argv[2];
  const workdir = process.argv[3];
  const model = process.argv[4] || "claude-sonnet-4-20250514";

  const agent = await Agent.create({
    prompt,
    workspace: workdir,
    model,
  });

  const result = [];
  for await (const event of agent.run.stream()) {
    if (event.type === "text") {
      result.push(event.text);
    }
  }

  const output = {
    text: result.join(""),
    usage: agent.run.usage || {},
    num_turns: agent.run.turns || 1,
  };

  process.stdout.write(JSON.stringify(output));
}

main().catch((err) => {
  process.stderr.write(err.message);
  process.exit(1);
});
"""


class CursorSdkRunner(BaseRunner):

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    @property
    def name(self) -> str:
        return "cursor_sdk"

    def run(self, prompt: str, workdir: Path, timeout: int = 300) -> RunnerResult:
        script_path = workdir / "_cursor_runner.js"
        script_path.write_text(CURSOR_RUNNER_SCRIPT)

        self._ensure_sdk(workdir)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                ["node", str(script_path), prompt, str(workdir), self.model],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
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
                error="node not found. Install Node.js 18+.",
                elapsed_seconds=0,
            )

        raw = proc.stdout
        files_created = collect_created_files(workdir)
        code = self._extract_code(raw, files_created)

        tokens_in, tokens_out, turns = 0, 0, 1
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                tokens_in = data.get("usage", {}).get("input_tokens", 0)
                tokens_out = data.get("usage", {}).get("output_tokens", 0)
                turns = data.get("num_turns", 1)
                raw = data.get("text", raw)
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

    def _ensure_sdk(self, workdir: Path):
        node_modules = workdir / "node_modules" / "@cursor" / "sdk"
        if not node_modules.exists():
            subprocess.run(
                ["npm", "install", "--no-save", "@cursor/sdk"],
                cwd=str(workdir),
                capture_output=True,
                timeout=60,
            )

    def _extract_code(self, raw_output: str, files: dict[str, str]) -> str:
        # Only Python counts as extracted code (see claude_code runner).
        py_files = {name: c for name, c in files.items() if name.endswith(".py")}
        if py_files:
            main_candidates = ["app.py", "main.py", "rag.py", "pipeline.py"]
            for candidate in main_candidates:
                if candidate in py_files:
                    return py_files[candidate]
            return "\n\n".join(py_files.values())
        return self.extract_python_from_output(raw_output)
