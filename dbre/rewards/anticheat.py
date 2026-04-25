from __future__ import annotations

import re


DANGEROUS_KEYWORDS = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE", "GRANT", "REVOKE"]


def normalize_sql(query: str) -> str:
    normalized = query.strip().upper()
    normalized = re.sub(r';\s*$', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def compute_anticheat(original_query: str, new_query: str) -> float:
    new_normalized = normalize_sql(new_query)
    orig_normalized = normalize_sql(original_query)

    if new_normalized == orig_normalized:
        return 0.0

    for keyword in DANGEROUS_KEYWORDS:
        if keyword in new_normalized:
            return 0.0

    if new_normalized in ("SELECT 1", "SELECT 1;", "", "SELECT 1 ;"):
        return 0.0

    if new_normalized.startswith("--") or new_normalized.startswith("/*"):
        return 0.0

    return 1.0
