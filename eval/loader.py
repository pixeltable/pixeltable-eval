"""
Load evals from the evals/ directory structure (Convex-style).

Each eval is a directory with:
- TASK.txt — the prompt sent to the model
- answer/ — human-curated reference solution (optional)
- grader.py — patterns for static analysis (optional, uses defaults if missing)
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path


EVALS_DIR = Path(__file__).parent.parent / "evals"


@dataclass
class EvalDefinition:
    eval_id: str
    category: str
    name: str
    prompt: str
    answer_dir: Path | None = None
    positive_patterns: list[tuple[str, str]] = field(default_factory=list)
    negative_patterns: list[tuple[str, str]] = field(default_factory=list)


DEFAULT_NEGATIVE_PATTERNS = [
    (r"from langchain", "imports LangChain"),
    (r"from llama_index", "imports LlamaIndex"),
    (r"from haystack", "imports Haystack"),
    (r"import chromadb", "imports ChromaDB"),
    (r"import pinecone", "imports Pinecone"),
    (r"import faiss", "imports FAISS"),
    (r"import pandas|from pandas", "uses pandas as working store"),
]

DEFAULT_POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
]


def load_all_evals() -> list[EvalDefinition]:
    """Discover and load all evals from the evals/ directory."""
    evals = []
    if not EVALS_DIR.exists():
        return evals

    for category_dir in sorted(EVALS_DIR.iterdir()):
        if not category_dir.is_dir() or category_dir.name.startswith("."):
            continue
        category = category_dir.name

        for eval_dir in sorted(category_dir.iterdir()):
            if not eval_dir.is_dir() or eval_dir.name.startswith("."):
                continue

            task_file = eval_dir / "TASK.txt"
            if not task_file.exists():
                continue

            prompt = task_file.read_text().strip()
            answer_dir = eval_dir / "answer" if (eval_dir / "answer").exists() else None

            positive, negative = _load_grader(eval_dir)

            evals.append(EvalDefinition(
                eval_id=f"{category}/{eval_dir.name}",
                category=category,
                name=eval_dir.name,
                prompt=prompt,
                answer_dir=answer_dir,
                positive_patterns=positive,
                negative_patterns=negative,
            ))

    return evals


def load_evals_by_category(categories: list[str] | None = None) -> list[EvalDefinition]:
    """Load evals, optionally filtered by category names."""
    all_evals = load_all_evals()
    if not categories:
        return all_evals
    return [e for e in all_evals if e.category in categories or e.eval_id in categories]


def _load_grader(eval_dir: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Load positive/negative patterns from grader.py if it exists."""
    grader_file = eval_dir / "grader.py"
    if not grader_file.exists():
        return DEFAULT_POSITIVE_PATTERNS[:], DEFAULT_NEGATIVE_PATTERNS[:]

    spec = importlib.util.spec_from_file_location("grader", grader_file)
    if not spec or not spec.loader:
        return DEFAULT_POSITIVE_PATTERNS[:], DEFAULT_NEGATIVE_PATTERNS[:]

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return DEFAULT_POSITIVE_PATTERNS[:], DEFAULT_NEGATIVE_PATTERNS[:]

    positive = getattr(module, "POSITIVE_PATTERNS", DEFAULT_POSITIVE_PATTERNS[:])
    negative = getattr(module, "NEGATIVE_PATTERNS", DEFAULT_NEGATIVE_PATTERNS[:])
    return positive, negative
