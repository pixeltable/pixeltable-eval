"""
Environment setup for eval runs.

Each context level configures the workspace differently to test
how much each layer of documentation/tooling improves agent output.
"""

from __future__ import annotations

import shutil
import subprocess
from enum import Enum
from pathlib import Path


class ContextLevel(str, Enum):
    COLD = "cold"
    WITH_SKILL = "skill"
    WITH_MCP = "skill_mcp"


def setup_environment(workdir: Path, context: ContextLevel, fixture_dir: Path | None = None):
    """Configure a workspace directory for a specific context level."""
    workdir.mkdir(parents=True, exist_ok=True)

    if fixture_dir and fixture_dir.exists():
        docs_dir = workdir / "docs"
        docs_dir.mkdir(exist_ok=True)
        for f in fixture_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, docs_dir / f.name)

    if context == ContextLevel.COLD:
        _setup_cold(workdir)
    elif context == ContextLevel.WITH_SKILL:
        _setup_with_skill(workdir)
    elif context == ContextLevel.WITH_MCP:
        _setup_with_skill_and_mcp(workdir)


def _setup_cold(workdir: Path):
    """Empty project — no hints, no skill, no docs."""
    pass


def _setup_with_skill(workdir: Path):
    """Install the pixeltable-skill via npx skills."""
    try:
        subprocess.run(
            ["npx", "-y", "skills", "add", "pixeltable/pixeltable-skill"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _setup_skill_manual(workdir)


def _setup_with_skill_and_mcp(workdir: Path):
    """Install skill + configure MCP server."""
    _setup_with_skill(workdir)

    mcp_config = {
        "mcpServers": {
            "pixeltable": {
                "command": "uvx",
                "args": ["mcp-server-pixeltable-developer"],
            }
        }
    }

    import json

    claude_dir = workdir / ".claude"
    claude_dir.mkdir(exist_ok=True)
    (claude_dir / "mcp.json").write_text(json.dumps(mcp_config, indent=2))

    cursor_dir = workdir / ".cursor"
    cursor_dir.mkdir(exist_ok=True)
    (cursor_dir / "mcp.json").write_text(json.dumps(mcp_config, indent=2))


def _setup_skill_manual(workdir: Path):
    """Fallback: clone the skill repo directly if npx fails."""
    skill_dir = workdir / ".skills" / "pixeltable-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "git", "clone", "--depth", "1",
                "https://github.com/pixeltable/pixeltable-skill.git",
                str(skill_dir),
            ],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    agents_md = workdir / "AGENTS.md"
    if not agents_md.exists():
        skill_md = skill_dir / "skills" / "pixeltable-skill" / "SKILL.md"
        if skill_md.exists():
            content = (
                "# AGENTS.md\n\n"
                "This project uses Pixeltable. See the skill for patterns:\n\n"
                f"Skill location: {skill_md}\n"
            )
            agents_md.write_text(content)
