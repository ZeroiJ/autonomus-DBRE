from __future__ import annotations

import re
from typing import Any


def fetch_explain_analyze(conn: Any, sql: str) -> str:
    """Return plain-text EXPLAIN (ANALYZE) output for ``sql``."""
    cur = conn.cursor()
    try:
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}")
        rows = cur.fetchall()
    finally:
        cur.close()
    return "\n".join(str(r[0]) for r in rows)


def summarize_explain(explain_text: str) -> str:
    """Short natural-language summary of scan types and index usage."""
    t = explain_text.lower()
    parts: list[str] = []

    seq = len(re.findall(r"seq scan", t))
    idx = len(re.findall(r"index (?:only )?scan", t))
    bitmap = len(re.findall(r"bitmap index scan", t))

    if seq:
        parts.append(f"{seq} sequential scan(s).")
    if idx:
        parts.append(f"{idx} index scan(s).")
    if bitmap:
        parts.append(f"{bitmap} bitmap index scan(s).")

    if "nested loop" in t:
        parts.append("Nested loop join(s).")
    if "hash join" in t:
        parts.append("Hash join(s).")
    if "merge join" in t:
        parts.append("Merge join(s).")

    if not parts:
        return "Review EXPLAIN output for plan details."
    return " ".join(parts)
