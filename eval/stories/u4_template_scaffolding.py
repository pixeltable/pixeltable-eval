"""
U4: Template-Based Project Scaffolding

Prompt: "Use a Pixeltable application template to build a video intelligence app."

Verifier checks:
- Static: uses --template flag, correct template name, uv sync, pxt serve
- Negative: no manual project creation, no LangChain/Flask, no --backend for template
"""

from __future__ import annotations

from eval.verifier import StoryVerifier


PROMPT = (
    "I want to build a video intelligence application using Pixeltable.\n\n"
    "Requirements:\n"
    "- Use `uvx pixeltable-new --template video-intel` to scaffold the project\n"
    "- The project name should be 'my-video-app'\n"
    "- After scaffolding, install dependencies with `uv sync`\n"
    "- Initialize the schema with `python schema.py`\n"
    "- Show how to start the API server\n"
    "- Demonstrate how to ingest a video and search for visual content\n"
    "- The template should handle frame extraction, audio transcription, "
    "object detection, and multi-modal search automatically via computed columns"
)


class U4TemplateScaffoldingVerifier(StoryVerifier):

    @property
    def story_id(self) -> str:
        return 'u4_template_scaffolding'

    @property
    def positive_patterns(self) -> list[tuple[str, str]]:
        return [
            (r'--template\s+video-intel', 'uses --template video-intel flag'),
            (r'uvx\s+pixeltable-new', 'uses pixeltable-new scaffolder'),
            (r'uv\s+sync', 'installs dependencies with uv'),
            (r'python\s+schema\.py', 'initializes schema'),
            (r'pxt\s+serve', 'runs pxt serve'),
            (r'frame_iterator|frame_extraction|frames', 'mentions frame extraction'),
            (r'transcri(be|ption)|whisper', 'mentions transcription'),
            (r'similarity\s*\(|search', 'demonstrates search capability'),
        ]

    @property
    def negative_patterns(self) -> list[tuple[str, str]]:
        return [
            (r'pip\s+install\s+pixeltable', 'manually installs pixeltable (should use scaffolder)'),
            (r'from langchain', 'imports LangChain'),
            (r'import chromadb', 'imports ChromaDB'),
            (r'from flask\s+import|from django', 'uses Flask/Django instead of pxt serve'),
            (r'mkdir\s.*&&.*touch\s', 'manually creates project structure'),
            (r'--backend.*--template|--template.*--backend', 'mixes --backend with --template'),
        ]
