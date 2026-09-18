"""
Base verifier interface and scoring utilities.

Supports three grading layers:
1. Static analysis (regex patterns) - fast, deterministic, brittle
2. LLM-as-judge (cross-model) - nuanced, handles valid variations
3. Functional execution (sandbox) - ground truth, slower

Composite score = static_weight * static + llm_weight * llm + functional_weight * functional
Default weights: 0.30 / 0.50 / 0.20

Partial credit: scores are continuous (0.0-5.0), not binary pass/fail.
A "pass" threshold can be configured but the raw score is always reported.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from eval.sandbox import PixeltableSandbox, SandboxResult


@dataclass
class VerificationResult:
    story_id: str
    # Composite
    score: float  # 0.0-5.0 composite
    passed: bool  # score >= pass_threshold
    # Per-layer
    static_score: float  # 0.0-5.0
    static_pass: bool
    llm_score: float | None  # 0.0-5.0, None if not run
    functional_pass: bool | None  # None = skipped
    # Detail
    idiomaticity: float  # 0-5 (from static signals)
    hallucination_count: int
    positive_hits: dict[str, bool] = field(default_factory=dict)
    negative_hits: dict[str, bool] = field(default_factory=dict)
    hallucinations_found: list[str] = field(default_factory=list)
    functional_details: dict = field(default_factory=dict)
    llm_details: dict = field(default_factory=dict)
    sandbox_result: SandboxResult | None = None


HALLUCINATED_APIS = [
    (r"openai\.vision\b", "openai.vision (does not exist)"),
    (r"from pixeltable\.iterators\s+import", "pixeltable.iterators (deprecated shim, use pixeltable.functions.*)"),
    (r"pxt\.Table\s*\(", "pxt.Table() (does not exist)"),
    (r"pxt\.load_table\b", "pxt.load_table (does not exist)"),
    (r"pxt\.connect\b", "pxt.connect (does not exist)"),
    (r"\.similarity\(\s*['\"]", ".similarity() positional string (use string= kwarg)"),
    (r"from pixeltable\s+import\s+Table\b", "from pixeltable import Table (wrong)"),
    (r"pxt\.Required\s*\[", "pxt.Required (does not exist; optional is T | None)"),
    (r"\bpxt\s+serve\b", "pxt serve (retired CLI; use pxt schema update + pxt service update)"),
    (r"\bpxt\s+service\s+run\b", "pxt service run (does not exist; use pxt service update)"),
    (r"\[+\s*tool\.pixeltable\.(serve|service)", "[tool.pixeltable.serve/service] TOML (does not exist)"),
    (r"\[\[\s*service\s*\]\]|\[\[\s*service\.routes\s*\]\]", "[[service]] TOML routes (retired; use FastAPIRouter)"),
    (r"uvx\s+pixeltable-new[^\n]*--(backend|serving|batch)\b", "pixeltable-new --backend/--serving/--batch (removed flags)"),
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
    (r"uvx\s+pixeltable-new|pxt\s+init\b", "scaffolds or initializes a project"),
    (r"TableModel|model_base\s*\(", "declares TableModel classes"),
    (r"__indexes__\s*=", "declares indexes on the model"),
    (r"FastAPIRouter|pixeltable\.serving", "uses FastAPIRouter for serving"),
    (r"add_(insert|update|delete|compute|query)_route\b", "declares serving routes"),
    (r"pxt\s+schema\s+update", "applies schema with pxt schema update"),
    (r"pxt\s+service\s+update", "starts the service with pxt service update"),
    (r"return_rows\s*=\s*True", "uses insert(return_rows=True)"),
]

# Weights for composite scoring
STATIC_WEIGHT = 0.30
LLM_WEIGHT = 0.50
FUNCTIONAL_WEIGHT = 0.20

PASS_THRESHOLD = 3.0  # Score >= 3.0/5.0 counts as "pass"


_COMMAND_BLOCK = re.compile(r"```(?:bash|sh|shell|console|zsh)\s*\n(.*?)```", re.DOTALL)


def command_evidence(transcript: str) -> str:
    """Pull executed/shown commands out of an agent transcript.

    Returns fenced bash/shell blocks plus tool-call lines (``⏺ ...`` in
    Claude Code text output). Prose is excluded so negative patterns only
    fire on things the agent actually ran or wrote down as commands, not
    on words it used to describe them.
    """
    if not transcript:
        return ""
    chunks = _COMMAND_BLOCK.findall(transcript)
    chunks += [ln for ln in transcript.splitlines() if ln.lstrip().startswith("⏺")]
    return "\n".join(chunks)


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

    def functional_check(self, sandbox: PixeltableSandbox) -> dict:
        """Run after code execution. Return {'pass': bool, ...details}.
        Override in subclass for story-specific checks. Default: skip."""
        return {"pass": None, "skipped": True}

    def verify(
        self,
        code: str,
        sandbox: PixeltableSandbox | None = None,
        llm_judge_result: dict | None = None,
        transcript: str = "",
        extra_evidence: str = "",
    ) -> VerificationResult:
        """Verify generated code with composite scoring.

        Args:
            code: Generated code (also executed when a sandbox is given)
            sandbox: Optional sandbox for functional execution
            llm_judge_result: Optional dict from LLMJudge.grade() with score fields
            transcript: Optional raw agent output. Commands it contains
                (tool calls, bash blocks) count as actions taken; the rest is
                only used as positive evidence, so describing an anti-pattern
                does not trigger it.
            extra_evidence: Optional contents of other files the agent
                created (configs, docs, scripts). Scored like code but never
                executed.
        """
        if not code or not code.strip():
            return VerificationResult(
                story_id=self.story_id,
                score=0.0,
                passed=False,
                static_score=0.0,
                static_pass=False,
                llm_score=None,
                functional_pass=None,
                idiomaticity=0.0,
                hallucination_count=0,
                functional_details={"error": "no code extracted"},
            )

        # --- Layer 1: Static analysis ---
        # Two evidence channels:
        # - actions: created files plus commands the agent ran or wrote down.
        #   Negative patterns, hallucinations, and idiom signals apply here so
        #   they only fire on things the agent actually did.
        # - evidence: actions plus the full transcript. Positive patterns apply
        #   here so mentioning a required tool or command counts as evidence.
        actions = code + "\n" + extra_evidence + "\n" + command_evidence(transcript)
        evidence = actions + "\n" + transcript

        positive_hits = {
            desc: bool(re.search(pattern, evidence, re.MULTILINE))
            for pattern, desc in self.positive_patterns
        }
        negative_hits = {
            desc: bool(re.search(pattern, actions, re.MULTILINE))
            for pattern, desc in self.negative_patterns
        }
        hallucinations = [
            desc for pattern, desc in HALLUCINATED_APIS
            if re.search(pattern, actions, re.MULTILINE)
        ]
        idiom_count = sum(
            1 for pattern, _ in IDIOMATICITY_SIGNALS
            if re.search(pattern, actions, re.MULTILINE)
        )
        idiomaticity = min(5.0, idiom_count * 5.0 / len(IDIOMATICITY_SIGNALS))

        # Static score: positive coverage - negative penalty - hallucination penalty
        pos_count = sum(positive_hits.values())
        pos_total = max(1, len(positive_hits))
        neg_fired = sum(negative_hits.values())

        static_raw = (pos_count / pos_total) * 5.0
        static_raw -= neg_fired * 1.0  # each anti-pattern costs 1 point
        static_raw -= len(hallucinations) * 0.5  # each hallucination costs 0.5
        static_score = max(0.0, min(5.0, static_raw))

        static_pass = all(positive_hits.values()) and not any(negative_hits.values())

        # --- Layer 2: LLM Judge (if provided) ---
        llm_score: float | None = None
        llm_details: dict = {}
        if llm_judge_result:
            llm_score = llm_judge_result.get("composite_score", 0.0)
            llm_details = llm_judge_result

        # --- Layer 3: Functional execution (if sandbox provided) ---
        sandbox_result = None
        functional: dict = {"pass": None, "skipped": True}
        functional_score = 0.0

        if sandbox:
            sandbox_result = sandbox.exec_code(code)
            if sandbox_result.success:
                try:
                    functional = self.functional_check(sandbox)
                    functional_score = 5.0 if functional.get("pass") else 2.0
                except Exception as e:
                    functional = {"pass": False, "error": str(e)}
                    functional_score = 1.0
            else:
                functional = {
                    "pass": False,
                    "exec_failed": True,
                    "exit_code": sandbox_result.exit_code,
                    "stderr_snippet": sandbox_result.stderr[:300],
                }
                functional_score = 0.0

        functional_pass = functional.get("pass")

        # --- Composite score ---
        if llm_score is not None and sandbox:
            # All three layers available
            score = (
                STATIC_WEIGHT * static_score +
                LLM_WEIGHT * llm_score +
                FUNCTIONAL_WEIGHT * functional_score
            )
        elif llm_score is not None:
            # Static + LLM (no sandbox)
            adjusted_static_w = STATIC_WEIGHT / (STATIC_WEIGHT + LLM_WEIGHT)
            adjusted_llm_w = LLM_WEIGHT / (STATIC_WEIGHT + LLM_WEIGHT)
            score = adjusted_static_w * static_score + adjusted_llm_w * llm_score
        elif sandbox:
            # Static + functional (no LLM)
            adjusted_static_w = STATIC_WEIGHT / (STATIC_WEIGHT + FUNCTIONAL_WEIGHT)
            adjusted_func_w = FUNCTIONAL_WEIGHT / (STATIC_WEIGHT + FUNCTIONAL_WEIGHT)
            score = adjusted_static_w * static_score + adjusted_func_w * functional_score
        else:
            # Static only
            score = static_score

        passed = score >= PASS_THRESHOLD

        return VerificationResult(
            story_id=self.story_id,
            score=score,
            passed=passed,
            static_score=static_score,
            static_pass=static_pass,
            llm_score=llm_score,
            functional_pass=functional_pass,
            idiomaticity=idiomaticity,
            hallucination_count=len(hallucinations),
            positive_hits=positive_hits,
            negative_hits=negative_hits,
            hallucinations_found=hallucinations,
            functional_details=functional,
            llm_details=llm_details,
            sandbox_result=sandbox_result,
        )
