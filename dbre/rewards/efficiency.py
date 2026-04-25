from __future__ import annotations

import time
from typing import Any


def compute_efficiency(baseline_latency_ms: float, optimized_latency_ms: float) -> float:
    if baseline_latency_ms <= 0:
        return 0.0

    improvement = (baseline_latency_ms - optimized_latency_ms) / baseline_latency_ms

    return max(-1.0, min(1.0, improvement))


def measure_latency(connection: Any, query: str) -> float:
    if not connection:
        return 0.0

    try:
        start = time.perf_counter()
        with connection.cursor() as cur:
            cur.execute(query)
            cur.fetchall()
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000
        return round(elapsed_ms, 3)
    except Exception as e:
        print(f"[EFFICIENCY] Error measuring latency: {e}")
        return 0.0


def measure_latency_with_explain(connection: Any, query: str) -> float:
    if not connection:
        return 0.0

    try:
        explain_query = f"EXPLAIN (ANALYZE, TIMING, FORMAT TEXT) {query}"
        with connection.cursor() as cur:
            cur.execute(explain_query)
            rows = cur.fetchall()

        execution_time = 0.0
        for row in rows:
            line = row[0]
            if "Execution Time:" in line:
                parts = line.split("Execution Time:")
                if len(parts) > 1:
                    time_str = parts[1].strip().replace("ms", "").strip()
                    try:
                        execution_time = float(time_str)
                    except ValueError:
                        pass
                break

        return execution_time
    except Exception as e:
        print(f"[EFFICIENCY] Error with EXPLAIN ANALYZE: {e}")
        return measure_latency(connection, query)
