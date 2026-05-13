"""
Statistical utilities for eval result analysis.

Provides confidence intervals, significance tests, and effect sizes
to prevent over-interpreting small-sample results.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class ConfidenceInterval:
    point: float
    lower: float
    upper: float
    n: int
    confidence: float = 0.95

    def overlaps(self, other: ConfidenceInterval) -> bool:
        return self.lower <= other.upper and other.lower <= self.upper

    def __str__(self) -> str:
        return f"{self.point*100:.0f}% [{self.lower*100:.0f}-{self.upper*100:.0f}%] (n={self.n})"


def wilson_ci(successes: int, trials: int, confidence: float = 0.95) -> ConfidenceInterval:
    """Wilson score interval for binomial proportion.

    More accurate than normal approximation for small n or extreme proportions.
    """
    if trials == 0:
        return ConfidenceInterval(point=0.0, lower=0.0, upper=0.0, n=0, confidence=confidence)

    z = _z_score(confidence)
    p_hat = successes / trials
    n = trials

    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = z * math.sqrt((p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))) / denom

    return ConfidenceInterval(
        point=p_hat,
        lower=max(0.0, center - margin),
        upper=min(1.0, center + margin),
        n=trials,
        confidence=confidence,
    )


def pass_at_k(n_trials: int, n_successes: int, k: int = 1) -> float:
    """Probability of at least one success in k attempts.

    Uses the unbiased estimator: 1 - C(n-c, k) / C(n, k)
    where n = trials, c = successes.
    """
    if n_trials == 0 or k <= 0:
        return 0.0
    if n_successes >= n_trials:
        return 1.0
    if n_trials - n_successes < k:
        return 1.0

    result = 1.0
    for i in range(k):
        result *= (n_trials - n_successes - i) / (n_trials - i)
    return 1.0 - result


def pass_power_k(per_trial_rate: float, k: int) -> float:
    """pass^k: probability ALL k trials succeed.

    Measures consistency. High pass^k means reliable behavior.
    """
    if k <= 0:
        return 0.0
    return per_trial_rate ** k


def bootstrap_ci(
    values: list[float],
    confidence: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> ConfidenceInterval:
    """Bootstrap confidence interval for continuous metrics (e.g., idiomaticity)."""
    if not values:
        return ConfidenceInterval(point=0.0, lower=0.0, upper=0.0, n=0, confidence=confidence)

    rng = random.Random(seed)
    n = len(values)
    point = sum(values) / n

    means = []
    for _ in range(n_bootstrap):
        sample = [rng.choice(values) for _ in range(n)]
        means.append(sum(sample) / n)

    means.sort()
    alpha = 1 - confidence
    lower_idx = int(alpha / 2 * n_bootstrap)
    upper_idx = int((1 - alpha / 2) * n_bootstrap)

    return ConfidenceInterval(
        point=point,
        lower=means[lower_idx],
        upper=means[min(upper_idx, n_bootstrap - 1)],
        n=n,
        confidence=confidence,
    )


def fisher_exact_test(a: int, b: int, c: int, d: int) -> float:
    """Fisher's exact test p-value for 2x2 contingency table.

    Table layout:
        | success | failure |
    A   |    a    |    b    |
    B   |    c    |    d    |

    Returns one-sided p-value (A better than B).
    """
    n = a + b + c + d
    row1 = a + b
    row2 = c + d
    col1 = a + c

    p_cutoff = _hypergeometric_pmf(a, n, row1, col1)
    p_value = 0.0

    for x in range(min(row1, col1) + 1):
        p = _hypergeometric_pmf(x, n, row1, col1)
        if p <= p_cutoff + 1e-10:
            p_value += p

    return min(1.0, p_value)


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size for comparing two proportions.

    |h| interpretation: 0.2 = small, 0.5 = medium, 0.8 = large.
    """
    phi1 = 2 * math.asin(math.sqrt(p1))
    phi2 = 2 * math.asin(math.sqrt(p2))
    return phi1 - phi2


def minimum_reps_needed(
    expected_diff: float = 0.30,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Approximate minimum reps per cell for detecting a given lift.

    Uses normal approximation for two-proportion z-test.
    """
    z_alpha = _z_score(1 - alpha)
    z_beta = _z_score(power)

    p1 = 0.5
    p2 = p1 + expected_diff
    p_bar = (p1 + p2) / 2

    numerator = (z_alpha * math.sqrt(2 * p_bar * (1 - p_bar)) +
                 z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    denominator = (p2 - p1) ** 2

    return max(3, math.ceil(numerator / denominator))


def classify_infra_error(error: str | None) -> bool:
    """Return True if the error is an infrastructure/environment issue, not a capability failure."""
    if not error:
        return False
    infra_markers = [
        "Configuration error",
        "JSON Parse error",
        "ECONNREFUSED",
        "ETIMEDOUT",
        "rate limit",
        "socket hang up",
        "ENOMEM",
        "OOM",
        "disk full",
        "permission denied",
        "claude CLI not found",
    ]
    error_lower = error.lower()
    return any(marker.lower() in error_lower for marker in infra_markers)


def _z_score(confidence: float) -> float:
    """Approximate z-score for a given confidence level."""
    # Common values
    z_table = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576, 0.80: 1.282}
    if confidence in z_table:
        return z_table[confidence]
    # Rational approximation (Abramowitz & Stegun 26.2.23)
    p = (1 + confidence) / 2
    t = math.sqrt(-2 * math.log(1 - p))
    return t - (2.515517 + 0.802853 * t + 0.010328 * t**2) / (
        1 + 1.432788 * t + 0.189269 * t**2 + 0.001308 * t**3
    )


def _hypergeometric_pmf(k: int, N: int, K: int, n: int) -> float:
    """P(X=k) for hypergeometric distribution."""
    try:
        return (
            math.comb(K, k) * math.comb(N - K, n - k) / math.comb(N, n)
        )
    except (ValueError, ZeroDivisionError):
        return 0.0
