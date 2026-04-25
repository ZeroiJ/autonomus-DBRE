from __future__ import annotations

import random
from typing import List

import psycopg2


class SchemaDrifter:
    """Applies random schema mutations to simulate production drift."""

    def __init__(self, connection):
        self.conn = connection
        self.applied_drifts: List[str] = []
        self._mutation_count = 0
        random.seed(42)

    def apply_random_drift(self) -> str:
        self.conn.rollback()  # Clear any failed transaction
        mutations = [
            self._add_column,
            self._drop_column,
            self._rename_column,
            self._create_index,
            self._drop_index,
        ]
        mutation = random.choice(mutations)
        drift_description = mutation()
        self.applied_drifts.append(drift_description)
        print(f"Applied drift: {drift_description}")
        return drift_description

    def get_schema_diff(self) -> List[str]:
        return self.applied_drifts.copy()

    def reset(self) -> None:
        """Drop all applied drifts by recreating tables."""
        cur = self.conn.cursor()
        cur.execute("DROP TABLE IF EXISTS reviews, order_items, orders, products, customers CASCADE;")
        self.conn.commit()
        cur.close()
        self.applied_drifts = []

    def _add_column(self) -> str:
        tables = ["customers", "products", "orders"]
        table = random.choice(tables)
        col_name = f"drift_col_{random.randint(1000, 9999)}"
        cur = self.conn.cursor()
        cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} VARCHAR(255) DEFAULT NULL;")
        self.conn.commit()
        cur.close()
        return f"ADD COLUMN {col_name} TO {table}"

    def _drop_column(self) -> str:
        safe_drops = {"customers": ["city"], "products": ["stock"], "orders": ["status"]}
        table = random.choice(list(safe_drops.keys()))
        cols = safe_drops[table]
        col = random.choice(cols)
        cur = self.conn.cursor()
        try:
            cur.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {col};")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
        cur.close()
        return f"DROP COLUMN {col} FROM {table}"

    def _rename_column(self) -> str:
        tables_cols = {"customers": "city", "products": "category", "orders": "status"}
        table = random.choice(list(tables_cols.keys()))
        old_col = tables_cols[table]
        new_col = f"{old_col}_v{random.randint(100, 999)}"
        cur = self.conn.cursor()
        try:
            cur.execute(f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col};")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
        cur.close()
        return f"RENAME COLUMN {table}.{old_col} TO {new_col}"

    def _create_index(self) -> str:
        tables_cols = {"customers": "email", "products": "category", "orders": "customer_id",
                       "order_items": "order_id", "reviews": "customer_id"}
        table = random.choice(list(tables_cols.keys()))
        col = tables_cols[table]
        idx_name = f"idx_{table}_{col}"
        cur = self.conn.cursor()
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({col});")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
        cur.close()
        return f"CREATE INDEX {idx_name} ON {table}({col})"

    def _drop_index(self) -> str:
        cur = self.conn.cursor()
        cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND indexname LIKE 'idx_%';")
        indexes = [row[0] for row in cur.fetchall()]
        cur.close()
        if not indexes:
            return self._create_index()
        idx = random.choice(indexes)
        cur = self.conn.cursor()
        try:
            cur.execute(f"DROP INDEX IF EXISTS {idx};")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
        cur.close()
        return f"DROP INDEX {idx}"
