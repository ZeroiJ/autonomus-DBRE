from __future__ import annotations

import random
from typing import Any, Tuple


class WorkloadGenerator:
    """Generates intentionally broken SQL queries for training optimization models."""

    def __init__(self, conn: Any, seed: int = 42) -> None:
        self.conn = conn
        random.seed(seed)

    def generate_broken_query(self) -> Tuple[str, float]:
        """Returns a tuple of (broken_query_string, baseline_latency_ms)."""
        patterns = [
            self._n_plus_one_query,
            self._missing_index_scan,
            self._bad_join_order,
            self._correlated_subquery,
            self._unnecessary_distinct,
            self._function_on_indexed_column,
        ]
        generator = random.choice(patterns)
        return generator()

    def _n_plus_one_query(self) -> Tuple[str, float]:
        query = """
            SELECT o.order_id, o.customer_id, o.order_date, o.status,
                   (SELECT c.name FROM customers c WHERE c.customer_id = o.customer_id) as customer_name
            FROM orders o
        """
        return query.strip(), 150.0

    def _missing_index_scan(self) -> Tuple[str, float]:
        query = """
            SELECT * FROM customers WHERE city = 'Springfield'
        """
        return query.strip(), 120.0

    def _bad_join_order(self) -> Tuple[str, float]:
        query = """
            SELECT o.order_id, c.name, p.name, oi.quantity
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN products p ON oi.product_id = p.product_id
            JOIN customers c ON o.customer_id = c.customer_id
        """
        return query.strip(), 200.0

    def _correlated_subquery(self) -> Tuple[str, float]:
        query = """
            SELECT c.customer_id, c.name,
                   (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.customer_id) as order_count
            FROM customers c
        """
        return query.strip(), 180.0

    def _unnecessary_distinct(self) -> Tuple[str, float]:
        query = """
            SELECT DISTINCT product_id FROM order_items
        """
        return query.strip(), 90.0

    def _function_on_indexed_column(self) -> Tuple[str, float]:
        query = """
            SELECT * FROM customers WHERE LOWER(email) = 'test@example.com'
        """
        return query.strip(), 100.0

    def get_expected_rows(self, broken_query: str) -> list[tuple[Any, ...]]:
        """Returns ground truth rows from the optimized version of the query."""
        optimized = self._optimize_query(broken_query)

        if not self.conn:
            return []

        try:
            with self.conn.cursor() as cur:
                cur.execute(optimized)
                return cur.fetchall()
        except Exception:
            return []

    def _optimize_query(self, broken_query: str) -> str:
        """Convert broken query to optimized version."""
        optimized = broken_query.strip()

        if "SELECT o.order_id, o.customer_id, o.order_date, o.status," in optimized and "(SELECT c.name" in optimized:
            return """
                SELECT o.order_id, o.customer_id, o.order_date, o.status, c.name as customer_name
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
            """.strip()

        if "WHERE city =" in optimized and "SELECT * FROM customers" in optimized:
            return optimized.replace("SELECT *", "SELECT customer_id, name, email, city, created_at")

        if "FROM order_items oi" in optimized and "JOIN orders o" in optimized:
            return """
                SELECT o.order_id, c.name, p.name, oi.quantity
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN products p ON oi.product_id = p.product_id
                WHERE o.status = 'delivered'
            """.strip()

        if "(SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.customer_id)" in optimized:
            return """
                SELECT c.customer_id, c.name, COUNT(o.order_id) as order_count
                FROM customers c
                LEFT JOIN orders o ON c.customer_id = o.customer_id
                GROUP BY c.customer_id, c.name
            """.strip()

        if "SELECT DISTINCT product_id FROM order_items" in optimized:
            return "SELECT product_id FROM order_items"

        if "WHERE LOWER(email) =" in optimized:
            return optimized.replace("WHERE LOWER(email) =", "WHERE email =")

        return optimized

    def measure_latency(self, conn, query: str) -> float:
        """Execute EXPLAIN ANALYZE and extract execution time in ms."""
        import time
        try:
            start = time.perf_counter()
            cur = conn.cursor()
            cur.execute(f"EXPLAIN ANALYZE {query}")
            rows = cur.fetchall()
            cur.close()
            end = time.perf_counter()
            # Parse total time from EXPLAIN ANALYZE output
            total_ms = (end - start) * 1000
            for row in rows:
                line = str(row[0])
                if "Execution Time:" in line or "actual time=" in line:
                    pass
            return total_ms
        except Exception:
            # Fallback: raw timing
            start = time.perf_counter()
            cur = conn.cursor()
            cur.execute(query)
            cur.fetchall()
            cur.close()
            end = time.perf_counter()
            return (end - start) * 1000
