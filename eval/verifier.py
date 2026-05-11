"""
Base verifier interface and scoring utilities.

Each story implements a StoryVerifier subclass with its own positive patterns,
negative patterns, and functional checks. The base class provides the static
analysis (grep-based) and scoring framework.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from eval.sandbox import PixeltableSandbox, SandboxResult


@dataclass
class VerificationResult:
    story_id: str
    passed: bool
    static_pass: bool
    functional_pass: bool
    idiomaticity: float  # 0-5
    hallucination_count: int
    positive_hits: dict[str, bool] = field(default_factory=dict)
    negative_hits: dict[str, bool] = field(default_factory=dict)
    hallucinations_found: list[str] = field(default_factory=list)
    functional_details: dict = field(default_factory=dict)
    sandbox_result: SandboxResult | None = None


HALLUCINATED_APIS = [
    (r"openai\.vision\b", "openai.vision (does not exist)"),
    (r"from pixeltable\.iterators\s+import\s+FrameIterator", "FrameIterator (deprecated import)"),
    (r"pxt\.Table\s*\(", "pxt.Table() (does not exist)"),
    (r"pxt\.load_table\b", "pxt.load_table (does not exist)"),
    (r"pxt\.connect\b", "pxt.connect (does not exist)"),
    (r"\.similarity\(\s*['\"]", ".similarity() positional string (use string= kwarg)"),
    (r"from pixeltable\s+import\s+Table\b", "from pixeltable import Table (wrong)"),
]

IDIOMATICITY_SIGNALS = [
    (r"if_exists\s*=\s*['\"]ignore['\"]", "uses if_exists='ignore'"),
    (r"add_computed_column\s*\(", "uses computed columns"),
    (r"add_embedding_index\s*\(", "uses embedding index"),
    (r"\.similarity\s*\(\s*string\s*=", "uses similarity(string=) correctly"),
    (r"create_view\s*\(", "uses views"),
    (r"from pixeltable\.functions\.", "imports from pixeltable.functions"),
    (r"\.collect\(\)", "calls .collect()"),
    (r"pxt\.create_dir\s*\(", "creates directory namespace"),
    (r"@pxt\.(udf|query)\b", "defines UDF or query function"),
    (r"\.choices\[0\]\.message\.content", "extracts OpenAI response correctly"),
]


class StoryVerifier(ABC):
    """Base class for per-story verification."""

    @property
    @abstractmethod
    def story_id(self) -> str: ...

    @property
    @abstractmethod
    def positive_patterns(self) -> list[tuple[str, str]]:
        """(regex, description) pairs that SHOULD appear in correct code."""
        ...

    @property
    @abstractmethod
    def negative_patterns(self) -> list[tuple[str, str]]:
        """(regex, description) pairs that should NOT appear."""
        ...

    @abstractmethod
    def functional_check(self, sandbox: PixeltableSandbox) -> dict:
        """Run after code execution. Return {'pass': bool, ...details}."""
        ...

    def verify(self, code: str, sandbox: PixeltableSandbox) -> VerificationResult:
        positive_hits = {
            desc: bool(re.search(pattern, code, re.MULTILINE))
            for pattern, desc in self.positive_patterns
        }
        negative_hits = {
            desc: bool(re.search(pattern, code, re.MULTILINE))
            for pattern, desc in self.negative_patterns
        }
        hallucinations = [
            desc for pattern, desc in HALLUCINATED_APIS
            if re.search(pattern, code, re.MULTILINE)
        ]
        idiom_score = sum(
            1 for pattern, _ in IDIOMATICITY_SIGNALS
            if re.search(pattern, code, re.MULTILINE)
        )
        idiomaticity = min(5.0, idiom_score * 5.0 / len(IDIOMATICITY_SIGNALS))

        static_pass = all(positive_hits.values()) and not any(negative_hits.values())

        sandbox_result = sandbox.exec_code(code)

        functional = {"pass": False, "skipped": True}
        if sandbox_result.success:
            try:
                functional = self.functional_check(sandbox)
            except Exception as e:
                functional = {"pass": False, "error": str(e)}

        return VerificationResult(
            story_id=self.story_id,
            passed=static_pass and sandbox_result.success and functional.get("pass", False),
            static_pass=static_pass,
            functional_pass=functional.get("pass", False),
            idiomaticity=idiomaticity,
            hallucination_count=len(hallucinations),
            positive_hits=positive_hits,
            negative_hits=negative_hits,
            hallucinations_found=hallucinations,
            functional_details=functional,
            sandbox_result=sandbox_result,
        )
