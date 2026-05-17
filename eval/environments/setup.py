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
    WITH_PLUGIN = "plugin"


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
    elif context == ContextLevel.WITH_PLUGIN:
        _setup_with_plugin(workdir)


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


def _setup_with_plugin(workdir: Path):
    """Install the pixeltable-skill via Claude Code marketplace plugin.

    This simulates the install path: /plugin marketplace add pixeltable/pixeltable-skill
    Since we can't drive Claude Code's plugin system programmatically, we clone
    the plugin repo and set up the .claude-plugin structure that Claude Code
    would create after marketplace install.
    """
    plugin_dir = workdir / ".claude-plugin"
    plugin_dir.mkdir(exist_ok=True)

    try:
        subprocess.run(
            [
                "git", "clone", "--depth", "1",
                "https://github.com/pixeltable/pixeltable-skill.git",
                str(workdir / ".pixeltable-skill-src"),
            ],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _setup_with_skill(workdir)
        return

    src = workdir / ".pixeltable-skill-src"
    if not src.exists():
        _setup_with_skill(workdir)
        return

    skill_md = src / "skills" / "pixeltable-skill" / "SKILL.md"
    marketplace_json = src / ".claude-plugin" / "marketplace.json"

    if marketplace_json.exists():
        shutil.copy2(marketplace_json, plugin_dir / "marketplace.json")

    if skill_md.exists():
        skills_dir = workdir / "skills" / "pixeltable-skill"
        skills_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_md, skills_dir / "SKILL.md")

    agents_md = workdir / "AGENTS.md"
    if not agents_md.exists() and skill_md.exists():
        content = (
            "# AGENTS.md\n\n"
            "This project uses Pixeltable.\n\n"
            "## Installed Plugins\n\n"
            "- pixeltable-skill (via Claude Code marketplace)\n\n"
            f"Skill location: {skills_dir / 'SKILL.md'}\n"
        )
        agents_md.write_text(content)

    shutil.rmtree(src, ignore_errors=True)

    _setup_with_skill_and_mcp(workdir)


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
