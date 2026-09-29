"""
Generic verifier for evals loaded from the evals/ tree.

Each evals/<category>/<name>/ dir provides TASK.txt (the prompt) and an
optional grader.py (POSITIVE_PATTERNS / NEGATIVE_PATTERNS / EXECUTE_CODE).
The generic verifier grades statically; when the grader opts in with
EXECUTE_CODE = True the generated code also runs in the sandbox and a clean
exec counts as the functional layer.
"""

from __future__ import annotations

from eval.loader import EvalDefinition
from eval.sandbox import PixeltableSandbox
from eval.verifier import StoryVerifier


class GenericEvalVerifier(StoryVerifier):
    def __init__(self, definition: EvalDefinition):
        self._def = definition
        self.requires_sandbox = definition.execute_code

    @property
    def story_id(self) -> str:
        return self._def.eval_id

    @property
    def positive_patterns(self) -> list[tuple[str, str]]:
        return self._def.positive_patterns

    @property
    def negative_patterns(self) -> list[tuple[str, str]]:
        return self._def.negative_patterns

    def functional_check(self, sandbox: PixeltableSandbox) -> dict:
        # Only reached when the grader opted into execution and exec_code
        # already succeeded (exec failures are scored upstream in verify()).
        if not self._def.execute_code:
            return {"pass": None, "skipped": True}
        return {"pass": True, "reason": "generated code executed cleanly"}
