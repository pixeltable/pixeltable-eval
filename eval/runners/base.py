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
