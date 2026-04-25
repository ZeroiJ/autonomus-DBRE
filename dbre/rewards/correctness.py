from __future__ import annotations

from typing import Any


def compute_correctness(
    new_query: str,
    reference_rows: list,
    new_rows: list = None,
) -> float:
    """Compare new query results to reference rows."""
    if new_rows is None:
        return 1.0

    if len(new_rows) != len(reference_rows):
        return 0.0

    if len(new_rows) == 0 and len(reference_rows) == 0:
        return 1.0

    new_set = set(new_rows)
    ref_set = set(reference_rows)

    matching_rows = len(new_set & ref_set)

    if len(reference_rows) == 0:
        return 1.0

    return matching_rows / len(reference_rows)
