from __future__ import annotations

from typing import Any

from dbre.rewards.efficiency import compute_efficiency
from dbre.rewards.style import compute_style
from dbre.rewards.anticheat import compute_anticheat


def compute_total_reward(
    original_query: str,
    new_query: str,
    reference_rows: list,
    baseline_latency_ms: float,
    new_latency_ms: float,
    new_rows: list = None,
) -> dict[str, float]:
    c = _compute_correctness(new_query, reference_rows, new_rows)
    e = compute_efficiency(baseline_latency_ms, new_latency_ms)
    s = compute_style(new_query)
    a = compute_anticheat(original_query, new_query)

    total = 0.4 * c + 0.3 * e + 0.2 * s + 0.1 * a

    print(f"[REWARD] c={c:.3f} e={e:.3f} s={s:.3f} a={a:.3f} total={total:.3f}")

    return {
        "correctness": round(c, 3),
        "efficiency": round(e, 3),
        "style": round(s, 3),
        "anticheat": round(a, 3),
        "total": round(total, 3),
    }


def _compute_correctness(new_query: str, reference_rows: list, new_rows: list = None) -> float:
    if new_rows is None:
        return 1.0
    if len(new_rows) != len(reference_rows):
        return 0.0
    if len(new_rows) == 0 and len(reference_rows) == 0:
        return 1.0
    new_set = set(new_rows)
    ref_set = set(reference_rows)
    if len(reference_rows) == 0:
        return 1.0
    return len(new_set & ref_set) / len(reference_rows)


__all__ = ["compute_total_reward"]
