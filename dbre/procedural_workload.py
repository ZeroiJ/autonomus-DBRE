"""
Procedural random generation of hard broken SQL for the e‑commerce schema.

Pairs each broken query with a semantically equivalent ``_last_clean`` SQL.
``get_expected_rows`` executes ``_last_clean`` when the broken text matches
the last generated episode.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

TABLE_COLUMNS: dict[str, list[str]] = {
    "customers": ["customer_id", "name", "email", "city", "created_at"],
    "products": ["product_id", "name", "category", "price", "stock"],
    "orders": ["order_id", "customer_id", "order_date", "status"],
    "order_items": ["item_id", "order_id", "product_id", "quantity", "unit_price"],
    "reviews": ["review_id", "customer_id", "product_id", "rating", "review_text", "created_at"],
}

ALL_TABLES = list(TABLE_COLUMNS.keys())

FK_NEIGHBORS: dict[str, list[str]] = {
    "customers": ["orders", "reviews"],
    "orders": ["customers", "order_items"],
    "order_items": ["orders", "products"],
    "products": ["order_items", "reviews"],
    "reviews": ["customers", "products"],
}

FK_ON = {
    ("customers", "orders"): ("customer_id", "customer_id"),
    ("orders", "customers"): ("customer_id", "customer_id"),
    ("orders", "order_items"): ("order_id", "order_id"),
    ("order_items", "orders"): ("order_id", "order_id"),
    ("order_items", "products"): ("product_id", "product_id"),
    ("products", "order_items"): ("product_id", "product_id"),
    ("customers", "reviews"): ("customer_id", "customer_id"),
    ("reviews", "customers"): ("customer_id", "customer_id"),
    ("products", "reviews"): ("product_id", "product_id"),
    ("reviews", "products"): ("product_id", "product_id"),
}

JOIN_TYPES = ("INNER", "LEFT", "RIGHT")


def _norm_sql(s: str) -> str:
    return " ".join(s.split())


@dataclass
class Alias:
    table: str
    name: str


class ProceduralWorkloadGenerator:
    """Hard‑mode procedural workload — novel broken queries each episode."""

    def __init__(self, conn: Any, seed: int = 42) -> None:
        self.conn = conn
        self._rng = random.Random(seed)
        self._ctr = 0
        self._last_broken: str | None = None
        self._last_clean: str | None = None
        try:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '5s'")
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    def _alias(self, table: str) -> str:
        self._ctr += 1
        return f"{table[0].lower()}{self._ctr}"

    def generate_broken_query(self) -> tuple[str, float]:
        for _ in range(12):
            self._ctr = 0
            try:
                self.conn.rollback()
                clean, broken = self._emit_pair()
                clean = _norm_sql(clean)
                broken = _norm_sql(broken)
                with self.conn.cursor() as cur:
                    cur.execute(clean)
                    cur.fetchall()
                with self.conn.cursor() as cur:
                    cur.execute(broken)
                    cur.fetchall()
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                continue
            self._last_clean = clean
            self._last_broken = broken
            return broken, self.measure_latency(self.conn, broken)

        c = Alias("customers", self._alias("customers"))
        o = Alias("orders", self._alias("orders"))
        clean = _norm_sql(
            f"SELECT {c.name}.customer_id, {o.name}.order_id FROM customers {c.name} "
            f"INNER JOIN orders {o.name} ON {o.name}.customer_id = {c.name}.customer_id LIMIT 200"
        )
        broken = _norm_sql(
            f"SELECT DISTINCT * FROM orders {o.name} LEFT JOIN customers {c.name} ON TRUE "
            f"WHERE LOWER({c.name}.email) LIKE '%@%'"
        )
        self._last_clean, self._last_broken = clean, broken
        return broken, self.measure_latency(self.conn, broken)

    def get_expected_rows(self, broken_query: str) -> list[tuple[Any, ...]]:
        if not self._last_broken or not self._last_clean:
            return []
        if _norm_sql(broken_query) != _norm_sql(self._last_broken):
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute(self._last_clean)
                return cur.fetchall()
        except Exception:
            return []

    def measure_latency(self, conn: Any, query: str) -> float:
        """Same as ``WorkloadGenerator.measure_latency``."""
        try:
            start = time.perf_counter()
            cur = conn.cursor()
            cur.execute(f"EXPLAIN ANALYZE {query}")
            cur.fetchall()
            cur.close()
            end = time.perf_counter()
            return (end - start) * 1000
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            start = time.perf_counter()
            cur = conn.cursor()
            cur.execute(query)
            cur.fetchall()
            cur.close()
            conn.commit()
            end = time.perf_counter()
            return (end - start) * 1000

    def _walk_refs(self, n: int) -> list[Alias]:
        rng = self._rng
        n = max(2, min(7, n))
        t = rng.choice(ALL_TABLES)
        refs = [Alias(t, self._alias(t))]
        for _ in range(n - 1):
            nxt = rng.choice(FK_NEIGHBORS[t])
            refs.append(Alias(nxt, self._alias(nxt)))
            t = nxt
        for tab in ALL_TABLES:
            if any(r.table == tab for r in refs):
                continue
            if rng.random() < 0.30 and tab in FK_NEIGHBORS[refs[-1].table]:
                refs.append(Alias(tab, self._alias(tab)))
        return refs[:7]

    def _join_cond(self, left: Alias, right: Alias) -> str | None:
        k = (left.table, right.table)
        if k in FK_ON:
            lc, rc = FK_ON[k]
            return f"{left.name}.{lc} = {right.name}.{rc}"
        k2 = (right.table, left.table)
        if k2 in FK_ON:
            lc, rc = FK_ON[k2]
            return f"{right.name}.{lc} = {left.name}.{rc}"
        return None

    def _chain_valid(self, seq: list[Alias]) -> bool:
        for i in range(1, len(seq)):
            if not self._join_cond(seq[i - 1], seq[i]):
                return False
        return True

    def _from_clauses(
        self, refs: list[Alias], rng: random.Random
    ) -> tuple[str, str, list[Alias]]:
        """Return (clean_from, broken_from, join order)."""
        seq = refs[:]
        if rng.random() < 0.5 and len(refs) > 1:
            rev = refs[::-1]
            if self._chain_valid(rev):
                seq = rev

        base = seq[0]
        clean = f"FROM {base.table} {base.name}"
        broken = f"FROM {base.table} {base.name}"
        for i in range(1, len(seq)):
            prev, curr = seq[i - 1], seq[i]
            fk = self._join_cond(prev, curr) or self._join_cond(curr, prev)
            jt = rng.choice(JOIN_TYPES)
            on_clause = fk or "TRUE"
            # Same join shape for clean vs broken so row‑count checks stay meaningful
            clean += f" {jt} JOIN {curr.table} {curr.name} ON {on_clause}"
            broken += f" {jt} JOIN {curr.table} {curr.name} ON {on_clause}"
        return clean, broken, seq

    def _emit_pair(self) -> tuple[str, str]:
        rng = self._rng
        n = rng.randint(2, 7)
        refs = self._walk_refs(n)

        clean_from, broken_from, seq = self._from_clauses(refs, rng)

        cols: list[str] = []
        for _ in range(rng.randint(1, min(6, len(seq) * 3))):
            a = rng.choice(seq)
            cols.append(f"{a.name}.{rng.choice(TABLE_COLUMNS[a.table])}")
        seen: set[str] = set()
        uniq = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        if not uniq:
            uniq = [f"{seq[0].name}.{TABLE_COLUMNS[seq[0].table][0]}"]

        sel_clean = "SELECT " + ", ".join(uniq)
        sel_br = sel_clean
        has_corr_sel = False
        if rng.randint(0, 3) > 0 and rng.random() < 0.35:
            cust = next((x for x in seq if x.table == "customers"), seq[0])
            sel_br = (
                f"SELECT {uniq[0]}, (SELECT COUNT(*) FROM orders o WHERE "
                f"o.customer_id = {cust.name}.customer_id) AS _cnt"
            )
            has_corr_sel = True

        if rng.random() < 0.40 and not has_corr_sel:
            sel_br = "SELECT *"

        if rng.random() < 0.25:
            sel_br = sel_br.replace("SELECT ", "SELECT DISTINCT ", 1)

        wc: list[str] = []
        wb: list[str] = []
        for _ in range(rng.randint(0, 8)):
            a = rng.choice(seq)
            col = rng.choice(TABLE_COLUMNS[a.table])
            op = rng.choice(["=", "!=", ">", "<", ">=", "<=", "LIKE", "IS NULL", "IS NOT NULL"])
            if op in ("IS NULL", "IS NOT NULL"):
                wc.append(f"{a.name}.{col} {op}")
                wb.append(f"{a.name}.{col} {op}")
                continue
            lc, lb = self._lit(col, op, rng)
            wc.append(f"{a.name}.{col} {op} {lc}")
            if rng.random() < 0.30 and col in ("email", "order_date", "created_at"):
                if col == "email":
                    wb.append(f"LOWER({a.name}.email) {op} LOWER({lb})")
                else:
                    wb.append(
                        f"EXTRACT(YEAR FROM {a.name}.{col}) {op} "
                        f"EXTRACT(YEAR FROM TIMESTAMP '2020-01-01')"
                    )
            elif rng.random() < 0.20:
                cust = next((x for x in seq if x.table == "customers"), None)
                if cust:
                    wb.append(
                        f"(SELECT COUNT(*) FROM orders o WHERE o.customer_id = {cust.name}.customer_id) <> 0"
                    )
                else:
                    wb.append(f"{a.name}.{col} {op} {lb}")
            else:
                wb.append(f"{a.name}.{col} {op} {lb}")

        wcs = " AND ".join(wc)
        wbs = " AND ".join(wb)

        if rng.random() < 0.05:
            wbs = ""

        group_sql = ""
        if rng.random() < 0.10:
            ax = rng.choice(seq)
            gc = next((c for c in TABLE_COLUMNS[ax.table] if "_id" in c), TABLE_COLUMNS[ax.table][0])
            group_sql = f" GROUP BY {ax.name}.{gc}"
            sel_clean = f"SELECT {ax.name}.{gc}, COUNT(*) AS _cnt"
            sel_br = sel_clean

        ord_sql = ""
        if rng.random() < 0.20 and len(seq) >= 2:
            a, b = rng.sample(seq, 2)
            ord_sql = (
                f" ORDER BY {a.name}.{rng.choice(TABLE_COLUMNS[a.table])}, "
                f"{b.name}.{rng.choice(TABLE_COLUMNS[b.table])} DESC"
            )

        lim_sql = ""
        if rng.random() < 0.15:
            lim_sql += f" LIMIT {rng.randint(1, 200)}"
        if rng.random() < 0.05:
            lim_sql += f" OFFSET {rng.randint(0, 40)}"

        clean_sql = f"{sel_clean} {clean_from}"
        if wcs:
            clean_sql += f" WHERE {wcs}"
        clean_sql += group_sql + ord_sql + lim_sql

        def _assemble_broken() -> str:
            q = f"{sel_br} {broken_from}"
            if wbs:
                q += f" WHERE {wbs}"
            q += group_sql + ord_sql + lim_sql
            return q

        broken_sql = _assemble_broken()

        def _ineff_score() -> int:
            n = 0
            su = sel_br.upper()
            if "DISTINCT" in su:
                n += 1
            if "SELECT *" in su:
                n += 1
            if "LOWER(" in broken_sql or "EXTRACT(" in broken_sql:
                n += 1
            if " RIGHT JOIN " in broken_sql.upper():
                n += 1
            if has_corr_sel:
                n += 1
            if not wbs:
                n += 1
            return n

        if _ineff_score() < 2:
            if "DISTINCT" not in sel_br.upper():
                sel_br = sel_br.replace("SELECT ", "SELECT DISTINCT ", 1)
            elif not has_corr_sel and "SELECT *" not in sel_br.upper():
                sel_br = "SELECT *"
            broken_sql = _assemble_broken()

        if _ineff_score() < 2:
            cx = next((x for x in seq if x.table == "customers"), seq[0])
            pred = f"LOWER({cx.name}.email) LIKE '%@%'"
            if " WHERE " in broken_sql:
                broken_sql = broken_sql.replace(" WHERE ", " WHERE " + pred + " AND ", 1)
            else:
                broken_sql += " WHERE " + pred

        # Hard cap row explosions from bad joins / ON TRUE (keeps EXPLAIN + fetch fast)
        if "LIMIT" not in clean_sql.upper():
            cap = f" LIMIT {rng.randint(50, 400)}"
            clean_sql += cap
            broken_sql += cap

        return clean_sql, broken_sql

    def _lit(self, col: str, op: str, rng: random.Random) -> tuple[str, str]:
        if col in ("name", "email", "city", "category", "status", "review_text"):
            v = rng.choice(["pending", "delivered", "%a%", "Springfield"])
            s = f"'{v}'"
            return s, s
        if col.endswith("_id"):
            n = rng.randint(1, 80)
            return str(n), str(n)
        if col in ("price", "unit_price"):
            n = rng.randint(5, 300)
            return str(n), str(n)
        if col in ("quantity", "stock", "rating"):
            n = rng.randint(1, 10)
            return str(n), str(n)
        if col in ("order_date", "created_at"):
            return "'2020-06-01'", "'2020-06-01'"
        return "'x'", "'x'"
