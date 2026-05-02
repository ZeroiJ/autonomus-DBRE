from __future__ import annotations

from typing import Any, Optional


def compute_correctness(reference_rows: list[Any], new_rows: Optional[list[Any]] = None) -> float:
    """1.0 if the agent query returns the same row count as the reference; 0.0 otherwise.

    When ``new_rows`` is None (e.g. index-only evaluation without a fresh fetch),
    correctness is not verified and defaults to 1.0.
    """
    if new_rows is None:
        return 1.0
    return 1.0 if len(new_rows) == len(reference_rows) else 0.0
