"""
LLM-as-Judge grader for evaluating generated Pixeltable code.

Uses a DIFFERENT model than the one being evaluated to avoid self-evaluation bias.
Scores across multiple dimensions with a structured rubric.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


RUBRIC = """\
You are an expert code reviewer evaluating Python code that uses the Pixeltable framework.
Score the code on each dimension from 1-5 using the rubric below.

## Dimensions

### Correctness (1-5)
1 = Code has fatal errors, won't run, or completely misunderstands the task
2 = Attempts the task but has significant bugs or missing steps
3 = Mostly correct but has notable issues (missing error handling, wrong API usage)
4 = Correct implementation with minor issues
5 = Fully correct, handles edge cases, would work in production

### Idiomaticity (1-5)
1 = Uses anti-patterns (LangChain, pandas as store, loops calling AI, separate vector DB)
2 = Uses Pixeltable but in non-idiomatic ways (manual batching, string manipulation for queries)
3 = Reasonable Pixeltable code but misses best practices (no if_exists, no views for splitting)
4 = Good idiomatic code, uses computed columns and embedding indexes properly
5 = Expert-level: uses if_exists='ignore', views with iterators, @pxt.query, proper namespacing

### Completeness (1-5)
1 = Only stub/skeleton code, doesn't address the task
2 = Addresses < 50% of requirements
3 = Addresses most requirements but missing important pieces
4 = Addresses all stated requirements
5 = Addresses all requirements plus handles edge cases, includes helpful structure

### Anti-Pattern Avoidance (1-5)
1 = Uses multiple anti-patterns (LangChain + pandas + vector DB + loops)
2 = Uses 1-2 significant anti-patterns
3 = No major anti-patterns but some suboptimal patterns
4 = Clean code, no anti-patterns
5 = Actively demonstrates the correct Pixeltable alternative to common anti-patterns

## Task Description
{task}

## Reference Solution (if available)
{reference}

## Generated Code to Evaluate
```python
{code}
```

## Response Format
Return ONLY a JSON object (no markdown, no explanation outside the JSON):
{{
  "correctness": <1-5>,
  "idiomaticity": <1-5>,
  "completeness": <1-5>,
  "anti_pattern_avoidance": <1-5>,
  "overall": <1-5>,
  "reasoning": "<brief 2-3 sentence explanation of scores>"
}}
"""


@dataclass
class LLMJudgeResult:
    correctness: float = 0.0
    idiomaticity: float = 0.0
    completeness: float = 0.0
    anti_pattern_avoidance: float = 0.0
    overall: float = 0.0
    reasoning: str = ""
    composite_score: float = 0.0
    raw_response: str = ""
    error: str | None = None


class LLMJudge:
    """Cross-model LLM judge for code quality assessment."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        if OpenAI is None:
            raise ImportError("openai package required: pip install openai")

        self.model = model
        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
        )

    def grade(
        self,
        code: str,
        task: str,
        reference: str | None = None,
    ) -> LLMJudgeResult:
        """Grade generated code against a task and optional reference solution."""
        if not code or not code.strip():
            return LLMJudgeResult(error="no code to grade")

        prompt = RUBRIC.format(
            task=task,
            reference=reference or "(no reference solution provided)",
            code=code,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
            )
            raw = response.choices[0].message.content or ""
        except Exception as e:
            return LLMJudgeResult(error=f"LLM judge API error: {e}")

        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> LLMJudgeResult:
        """Parse structured JSON response from judge."""
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return LLMJudgeResult(
                error=f"Failed to parse judge response as JSON",
                raw_response=raw,
            )

        correctness = float(data.get("correctness", 0))
        idiomaticity = float(data.get("idiomaticity", 0))
        completeness = float(data.get("completeness", 0))
        anti_pattern = float(data.get("anti_pattern_avoidance", 0))
        overall = float(data.get("overall", 0))
        reasoning = data.get("reasoning", "")

        # Weighted composite: correctness matters most
        composite = (
            correctness * 0.30 +
            idiomaticity * 0.25 +
            completeness * 0.20 +
            anti_pattern * 0.15 +
            overall * 0.10
        )

        return LLMJudgeResult(
            correctness=correctness,
            idiomaticity=idiomaticity,
            completeness=completeness,
            anti_pattern_avoidance=anti_pattern,
            overall=overall,
            reasoning=reasoning,
            composite_score=composite,
            raw_response=raw,
        )


def load_reference_solution(eval_dir: Path) -> str | None:
    """Load reference solution from answer/ directory."""
    answer_dir = eval_dir / "answer"
    if not answer_dir.exists():
        return None

    py_files = list(answer_dir.glob("*.py"))
    if not py_files:
        return None

    return "\n\n".join(f.read_text() for f in sorted(py_files))
