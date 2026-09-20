"""
Base runner interface.

A runner drives an AI coding agent (Claude Code, Cursor, Codex, etc.)
with a given prompt in a given environment, and returns the generated code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunnerResult:
    runner_name: str
    raw_output: str
    extracted_code: str
    files_created: dict[str, str] = field(default_factory=dict)  # filename -> content
    turns: int = 1
    tokens_in: int = 0
    tokens_out: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


COLLECT_EXTS = {".py", ".toml", ".md", ".txt", ".sh"}
SKIP_DIRS = {"node_modules", "site-packages", "__pycache__", "dist", "build"}


def collect_created_files(workdir: Path) -> dict[str, str]:
    """Collect agent-created text files that count as grading evidence.

    Anything under a hidden dir, a ``_``-prefixed dir, or a dependency/build
    dir is skipped: those are harness or vendored files, not agent output.
    Only Python files end up in ``extracted_code``; the rest still reach the
    verifier through ``files_created`` -> ``extra_evidence``.
    """
    files = {}
    for f in workdir.rglob("*"):
        if not f.is_file() or f.suffix not in COLLECT_EXTS:
            continue
        rel = f.relative_to(workdir)
        if rel.parts[0].startswith((".", "_")):
            continue
        if any(p in SKIP_DIRS or "venv" in p for p in rel.parts):
            continue
        # Skill payloads installed by env setup (npx skills add writes
        # agent/skills/**) are harness fixtures, not agent output.
        if len(rel.parts) >= 2 and rel.parts[1] == "skills" and rel.parts[0] in {"agent", "agents"}:
            continue
        try:
            content = f.read_text()
        except Exception:
            continue
        if content.strip():
            files[str(rel)] = content
    return files


class BaseRunner(ABC):
    """Interface for driving an AI coding agent."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, prompt: str, workdir: Path, timeout: int = 300) -> RunnerResult:
        """Execute the prompt in the agent and return generated code."""
        ...

    @staticmethod
    def extract_python_from_output(output: str) -> str:
        """Extract Python code blocks from agent output."""
        import re

        blocks = re.findall(r"```python\s*\n(.*?)```", output, re.DOTALL)
        if blocks:
            return "\n\n".join(blocks)

        blocks = re.findall(r"```\s*\n(.*?)```", output, re.DOTALL)
        python_blocks = [b for b in blocks if "import " in b or "def " in b or "pxt." in b]
        if python_blocks:
            return "\n\n".join(python_blocks)

        return output
