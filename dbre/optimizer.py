from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from dbre.explain_utils import fetch_explain_analyze, summarize_explain
from dbre.inference import generate_optimized_sql
from dbre.rewards import compute_total_reward
from dbre.procedural_workload import ProceduralWorkloadGenerator


@dataclass
class OptimizeOutcome:
    """Structured result from ``optimize_sql``."""

    original: str
    optimized: str
    baseline_latency_ms: float
    optimized_latency_ms: float
    improvement_pct: float
    reward_breakdown: dict[str, float]
    explain_summary: str
    explain_full: Optional[str] = None
    error: Optional[str] = None

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = asdict(self)
        if d.get("explain_full") is None:
            d.pop("explain_full", None)
        if d.get("error") is None:
            d.pop("error", None)
        return d


def _improvement_pct(baseline_ms: float, optimized_ms: float) -> float:
    if baseline_ms <= 0:
        return 0.0
    return round((baseline_ms - optimized_ms) / baseline_ms * 100.0, 2)


def _reward_breakdown_public(rb: dict[str, float]) -> dict[str, float]:
    """API-facing subset of reward keys."""
    keys = ("correctness", "efficiency", "style", "anticheat", "total")
    return {k: float(rb[k]) for k in keys if k in rb}


def optimize_sql(
    conn: Any,
    original_sql: str,
    model: Any,
    tokenizer: Any,
    *,
    include_explain_text: bool = False,
) -> OptimizeOutcome:
    """
    Execute baseline query, generate optimized SQL with the model, score with ``compute_total_reward``.
    """
    q = original_sql.strip()
    if not q:
        return OptimizeOutcome(
            original="",
            optimized="",
            baseline_latency_ms=0.0,
            optimized_latency_ms=0.0,
            improvement_pct=0.0,
            reward_breakdown={},
            explain_summary="",
            error="Empty query.",
        )

    if not q.endswith(";"):
        q += ";"
    original_sql = q
    sql_exec = original_sql.rstrip(";").strip()

    wg = ProceduralWorkloadGenerator(conn)
    cur = conn.cursor()
    try:
        cur.execute(sql_exec)
        reference_rows = cur.fetchall()
    except Exception as e:
        cur.close()
        return OptimizeOutcome(
            original=original_sql,
            optimized="",
            baseline_latency_ms=0.0,
            optimized_latency_ms=0.0,
            improvement_pct=0.0,
            reward_breakdown={},
            explain_summary="",
            error=f"Invalid SQL or execution error on original query: {e}",
        )
    cur.close()

    baseline_latency_ms = wg.measure_latency(conn, sql_exec)

    try:
        optimized_raw = generate_optimized_sql(model, tokenizer, sql_exec)
    except Exception as e:
        return OptimizeOutcome(
            original=original_sql,
            optimized="",
            baseline_latency_ms=baseline_latency_ms,
            optimized_latency_ms=0.0,
            improvement_pct=0.0,
            reward_breakdown={},
            explain_summary="",
            error=f"Model generation failed: {e}",
        )

    optimized_sql = optimized_raw.strip()
    if not optimized_sql.endswith(";"):
        optimized_sql += ";"

    cur = conn.cursor()
    try:
        cur.execute(optimized_sql.rstrip(";"))
        new_rows = cur.fetchall()
    except Exception as e:
        cur.close()
        return OptimizeOutcome(
            original=original_sql,
            optimized=optimized_sql,
            baseline_latency_ms=baseline_latency_ms,
            optimized_latency_ms=0.0,
            improvement_pct=0.0,
            reward_breakdown={},
            explain_summary="",
            error=f"Optimized SQL failed to execute: {e}",
        )
    cur.close()

    optimized_latency_ms = wg.measure_latency(conn, optimized_sql.rstrip(";"))
    rb = compute_total_reward(
        original_query=original_sql,
        new_query=optimized_sql,
        reference_rows=list(reference_rows),
        baseline_latency_ms=baseline_latency_ms,
        new_latency_ms=optimized_latency_ms,
        new_rows=list(new_rows),
    )
    public_rb = _reward_breakdown_public(rb)

    try:
        explain_text = fetch_explain_analyze(conn, optimized_sql.rstrip(";").strip())
        summary = summarize_explain(explain_text)
    except Exception as e:
        explain_text = ""
        summary = f"Could not run EXPLAIN ANALYZE: {e}"

    return OptimizeOutcome(
        original=original_sql,
        optimized=optimized_sql,
        baseline_latency_ms=round(baseline_latency_ms, 4),
        optimized_latency_ms=round(optimized_latency_ms, 4),
        improvement_pct=_improvement_pct(baseline_latency_ms, optimized_latency_ms),
        reward_breakdown=public_rb,
        explain_summary=summary,
        explain_full=explain_text if include_explain_text else None,
        error=None,
    )
