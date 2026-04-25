from __future__ import annotations

import re

import sqlparse


def is_valid_sql(query: str) -> bool:
    try:
        parsed = sqlparse.parse(query)
        return len(parsed) > 0 and parsed[0].tokens is not None
    except Exception:
        return False


def compute_style(query: str) -> float:
    if not is_valid_sql(query):
        return 0.0

    score = 0.0
    query_upper = query.upper()

    if "SELECT *" not in query_upper and "SELECT\n\t*" not in query_upper:
        score += 0.3

    join_count = query_upper.count(" JOIN ")
    alias_pattern = re.compile(r'\b\w+\s+AS\s+\w+\b', re.IGNORECASE)
    has_aliases = bool(alias_pattern.search(query)) or any(
        word in query_upper for word in [" AS A", " AS B", " AS C", " AS O", " AS P", " AS CUS", " AS PROD"]
    )
    if join_count > 0 and has_aliases:
        score += 0.2

    keywords = ["SELECT", "FROM", "WHERE", "JOIN", "GROUP BY", "ORDER BY", "HAVING", "LIMIT"]
    uppercase_count = sum(1 for kw in keywords if kw in query_upper)
    if uppercase_count >= len(keywords) * 0.7:
        score += 0.2

    lines = query.split("\n")
    has_indentation = any(line.startswith("  ") or line.startswith("\t") for line in lines)
    if has_indentation or len(lines) > 1:
        score += 0.1

    if "WHERE" in query_upper:
        score += 0.2

    return min(1.0, score)
