"""Canary: reference solutions must satisfy their own graders.

Each evals/<group>/<task>/ dir may carry an answer/ with known-good code.
If a grader's patterns stop matching the reference, the grader drifted --
the failure is in the harness, not in any agent.
"""

import importlib.util
import re
from pathlib import Path

import pytest

EVALS_DIR = Path(__file__).parent.parent / "evals"


def _load_grader(path: Path):
    spec = importlib.util.spec_from_file_location(f"grader_{path.parent.name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _canary_dirs():
    return sorted(
        d.parent for d in EVALS_DIR.rglob("answer")
        if (d.parent / "grader.py").exists()
    )


def test_canary_evals_exist():
    assert _canary_dirs(), "no evals with answer/ + grader.py found"


@pytest.mark.parametrize("eval_dir", _canary_dirs(), ids=lambda d: str(d.relative_to(EVALS_DIR)))
def test_reference_answer_passes_grader(eval_dir: Path):
    grader = _load_grader(eval_dir / "grader.py")
    code = "\n\n".join(
        f.read_text() for f in sorted((eval_dir / "answer").glob("*.py"))
    )
    assert code.strip(), f"{eval_dir}: answer/ has no .py files"

    missing = [
        desc for pattern, desc in grader.POSITIVE_PATTERNS
        if not re.search(pattern, code, re.MULTILINE)
    ]
    fired = [
        desc for pattern, desc in grader.NEGATIVE_PATTERNS
        if re.search(pattern, code, re.MULTILINE)
    ]
    assert not missing, f"{eval_dir}: reference misses positive patterns: {missing}"
    assert not fired, f"{eval_dir}: reference triggers negative patterns: {fired}"
