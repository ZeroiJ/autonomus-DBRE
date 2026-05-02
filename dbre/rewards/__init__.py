from __future__ import annotations

from typing import Any, Optional

from dbre.rewards.anticheat import compute_anticheat
from dbre.rewards.correctness import compute_correctness
from dbre.rewards.efficiency import compute_efficiency
from dbre.rewards.style import compute_style

# Correctness, efficiency, style, anticheat — total is clamped to [0, 1]
REWARD_WEIGHTS = (0.3, 0.4, 0.2, 0.1)


def weighted_total(c: float, e: float, s: float, a: float) -> float:
    """0.3×c + 0.4×e + 0.2×s + 0.1×a, clamped to [0, 1]."""
    t = (
        REWARD_WEIGHTS[0] * c
        + REWARD_WEIGHTS[1] * e
        + REWARD_WEIGHTS[2] * s
        + REWARD_WEIGHTS[3] * a
    )
    return max(0.0, min(1.0, t))


def weighted_total_from_breakdown(breakdown: dict[str, Any]) -> float:
    """Recompute the scalar reward from a ``reward_breakdown`` dict."""
    return weighted_total(
        float(breakdown.get("correctness", 0.0)),
        float(breakdown.get("efficiency", 0.0)),
        float(breakdown.get("style", 0.0)),
        float(breakdown.get("anticheat", 0.0)),
    )


def compute_total_reward(
    original_query: str,
    new_query: str,
    reference_rows: list,
    baseline_latency_ms: float,
    new_latency_ms: float,
    new_rows: Optional[list] = None,
) -> dict[str, float]:
    c = compute_correctness(reference_rows, new_rows)
    e_raw = compute_efficiency(baseline_latency_ms, new_latency_ms)
    # Map efficiency from [-1, 1] to [0, 1] so the weighted sum stays in [0, 1]
    e = max(0.0, min(1.0, (e_raw + 1.0) / 2.0))
    s = max(0.0, min(1.0, compute_style(new_query)))
    a = max(0.0, min(1.0, compute_anticheat(original_query, new_query)))

    total = weighted_total(c, e, s, a)

    print(f"[REWARD] c={c:.3f} e={e:.3f} (raw_eff={e_raw:.3f}) s={s:.3f} a={a:.3f} total={total:.3f}")

    return {
        "correctness": round(c, 3),
        "efficiency": round(e, 3),
        "efficiency_raw": round(e_raw, 3),
        "style": round(s, 3),
        "anticheat": round(a, 3),
        "total": round(total, 3),
    }


__all__ = [
    "compute_total_reward",
    "compute_correctness",
    "weighted_total",
    "weighted_total_from_breakdown",
    "REWARD_WEIGHTS",
]
