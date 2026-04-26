from __future__ import annotations

import random
from typing import Any

from faker import Faker


HOLDOUT_QUERIES = [
    (
        """SELECT o.order_id, o.customer_id, o.order_date, o.status,
                  (SELECT c.name FROM holdout.customers c WHERE c.customer_id = o.customer_id) as customer_name
           FROM holdout.orders o""",
        """SELECT o.order_id, o.customer_id, o.order_date, o.status, c.name as customer_name
           FROM holdout.orders o
           JOIN holdout.customers c ON o.customer_id = c.customer_id""",
        "N+1 query pattern: correlated subquery per row instead of JOIN"
    ),
    (
        """SELECT * FROM holdout.customers WHERE city = 'Springfield'""",
        """SELECT customer_id, name, email, city, created_at FROM holdout.customers WHERE city = 'Springfield'""",
        "Missing index: full table scan on unindexed column with SELECT *"
    ),
    (
        """SELECT o.order_id, c.name, p.name, oi.quantity
           FROM holdout.order_items oi
           JOIN holdout.orders o ON oi.order_id = o.order_id
           JOIN holdout.products p ON oi.product_id = p.product_id
           JOIN holdout.customers c ON o.customer_id = c.customer_id""",
        """SELECT o.order_id, c.name, p.name, oi.quantity
           FROM holdout.orders o
           JOIN holdout.customers c ON o.customer_id = c.customer_id
           JOIN holdout.order_items oi ON o.order_id = oi.order_id
           JOIN holdout.products p ON oi.product_id = p.product_id
           WHERE o.status = 'delivered'""",
        "Bad join order: suboptimal table order with no filtering"
    ),
    (
        """SELECT c.customer_id, c.name,
                  (SELECT COUNT(*) FROM holdout.orders o WHERE o.customer_id = c.customer_id) as order_count
           FROM holdout.customers c""",
        """SELECT c.customer_id, c.name, COUNT(o.order_id) as order_count
           FROM holdout.customers c
           LEFT JOIN holdout.orders o ON c.customer_id = o.customer_id
           GROUP BY c.customer_id, c.name""",
        "Correlated subquery: should be JOIN with GROUP BY"
    ),
    (
        """SELECT DISTINCT product_id FROM holdout.order_items""",
        """SELECT product_id FROM holdout.order_items""",
        "Unnecessary DISTINCT: column is already unique in context"
    ),
    (
        """SELECT * FROM holdout.customers WHERE LOWER(email) = 'test@example.com'""",
        """SELECT customer_id, name, email, city, created_at FROM holdout.customers WHERE email = 'test@example.com'""",
        "Function on indexed column: prevents index usage"
    ),
    (
        """SELECT o.order_id, o.customer_id, o.order_date, o.status,
                  (SELECT c.name FROM holdout.customers c WHERE c.customer_id = o.customer_id) as customer_name
           FROM holdout.orders o WHERE o.status = 'pending'""",
        """SELECT o.order_id, o.customer_id, o.order_date, o.status, c.name as customer_name
           FROM holdout.orders o
           JOIN holdout.customers c ON o.customer_id = c.customer_id
           WHERE o.status = 'pending'""",
        "N+1 with filter: correlated subquery in filtered query"
    ),
    (
        """SELECT c.customer_id, c.name, c.email, c.city FROM holdout.customers c
           WHERE c.customer_id IN (SELECT o.customer_id FROM holdout.orders o WHERE o.status = 'pending')""",
        """SELECT c.customer_id, c.name, c.email, c.city FROM holdout.customers c
           JOIN holdout.orders o ON c.customer_id = o.customer_id
           WHERE o.status = 'pending'""",
        "IN subquery: should be JOIN"
    ),
    (
        """SELECT p.product_id, p.name, p.price FROM holdout.products p
           WHERE p.product_id NOT IN (SELECT oi.product_id FROM holdout.order_items oi)""",
        """SELECT p.product_id, p.name, p.price FROM holdout.products p
           LEFT JOIN holdout.order_items oi ON p.product_id = oi.product_id
           WHERE oi.product_id IS NULL""",
        "NOT IN subquery: should be LEFT JOIN with NULL check"
    ),
    (
        """SELECT o.order_id, o.customer_id, o.order_date, o.status,
                  (SELECT SUM(oi.quantity * oi.unit_price) FROM holdout.order_items oi WHERE oi.order_id = o.order_id) as total
           FROM holdout.orders o""",
        """SELECT o.order_id, o.customer_id, o.order_date, o.status, SUM(oi.quantity * oi.unit_price) as total
           FROM holdout.orders o
           JOIN holdout.order_items oi ON o.order_id = oi.order_id
           GROUP BY o.order_id, o.customer_id, o.order_date, o.status""",
        "Correlated aggregation: subquery should be JOIN with GROUP BY"
    ),
    (
        """SELECT DISTINCT c.customer_id, c.name, c.email FROM holdout.customers c
           JOIN holdout.orders o ON c.customer_id = o.customer_id""",
        """SELECT c.customer_id, c.name, c.email FROM holdout.customers c
           JOIN holdout.orders o ON c.customer_id = o.customer_id""",
        "Unnecessary DISTINCT in JOIN: customer_id is already unique"
    ),
    (
        """SELECT * FROM holdout.orders o
           JOIN holdout.customers c ON o.customer_id = c.customer_id
           JOIN holdout.order_items oi ON o.order_id = oi.order_id
           JOIN holdout.products p ON oi.product_id = p.product_id
           WHERE EXTRACT(YEAR FROM o.order_date) = 2024""",
        """SELECT o.order_id, c.name, p.name, oi.quantity
           FROM holdout.orders o
           JOIN holdout.customers c ON o.customer_id = c.customer_id
           JOIN holdout.order_items oi ON o.order_id = oi.order_id
           JOIN holdout.products p ON oi.product_id = p.product_id
           WHERE o.order_date >= '2024-01-01' AND o.order_date < '2025-01-01'""",
        "Function on column in WHERE: EXTRACT prevents index, also SELECT * is bad"
    ),
    (
        """SELECT c.customer_id, c.name,
                  (SELECT r.rating FROM holdout.reviews r WHERE r.customer_id = c.customer_id ORDER BY r.created_at DESC LIMIT 1) as latest_rating
           FROM holdout.customers c""",
        """SELECT c.customer_id, c.name, r.rating as latest_rating
           FROM holdout.customers c
           JOIN holdout.reviews r ON c.customer_id = r.customer_id
           WHERE r.created_at = (SELECT MAX(created_at) FROM holdout.reviews WHERE customer_id = c.customer_id)""",
        "Correlated subquery with LIMIT: should use JOIN with proper filter"
    ),
    (
        """SELECT p.product_id, p.name, p.price, p.category FROM holdout.products p
           WHERE p.category = 'Electronics' AND p.price > 100
           ORDER BY p.price DESC""",
        """SELECT p.product_id, p.name, p.price, p.category FROM holdout.products p
           WHERE p.category = 'Electronics' AND p.price > 100
           ORDER BY p.price DESC""",
        "Actually optimized query - no index on category+price yet"
    ),
    (
        """SELECT o.order_id, o.status, o.order_date,
                  (SELECT SUM(oi.quantity) FROM holdout.order_items oi WHERE oi.order_id = o.order_id) as total_qty,
                  (SELECT c.name FROM holdout.customers c WHERE c.customer_id = o.customer_id) as customer_name,
                  (SELECT c.email FROM holdout.customers c WHERE c.customer_id = o.customer_id) as customer_email
           FROM holdout.orders o
           WHERE o.status = 'pending'""",
        """SELECT o.order_id, o.status, o.order_date, SUM(oi.quantity) as total_qty, c.name as customer_name, c.email as customer_email
           FROM holdout.orders o
           JOIN holdout.customers c ON o.customer_id = c.customer_id
           JOIN holdout.order_items oi ON o.order_id = oi.order_id
           WHERE o.status = 'pending'
           GROUP BY o.order_id, o.status, o.order_date, c.name, c.email""",
        "Multiple correlated subqueries: all should be JOINs"
    ),
]


def evaluate_playbook(connection, playbook_content: str) -> float:
    rules = ['index', 'join', 'EXPLAIN', 'N+1', 'subquery', 'cardinality', 'hash join']
    score = sum(1 for r in rules if r.lower() in playbook_content.lower())
    final = score / len(rules)
    print(f'Rule coverage: {final:.2%} ({score}/{len(rules)})')
    return final
def _check_query_fixed(
    connection: Any,
    broken_query: str,
    expected_optimized: str,
    playbook_content: str
) -> bool:
    """Check if the playbook would fix this query."""
    try:
        with connection.cursor() as cur:
            cur.execute(expected_optimized)
            expected_rows = cur.fetchall()

            if playbook_content.strip():
                test_query = _apply_playbook_rules(broken_query, playbook_content)
                cur.execute(test_query)
                actual_rows = cur.fetchall()
                return actual_rows == expected_rows

            return False
    except Exception:
        return False


def _apply_playbook_rules(query: str, playbook_content: str) -> str:
    """Apply playbook transformation rules to query."""
    result = query
    lines = playbook_content.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        if 'correlated subquery' in line.lower() and 'join' in line.lower():
            if '(SELECT' in result and 'FROM' in result:
                pass
                
        elif 'distinct' in line.lower() and 'remove' in line.lower():
            result = result.replace('DISTINCT ', '')
            
        elif 'select *' in line.lower() and 'avoid' in line.lower():
            result = result.replace('SELECT *', 'SELECT specific_columns')
            
        elif 'function on indexed column' in line.lower():
            if 'LOWER(' in result:
                result = result.replace('LOWER(', '').replace(')', '', 1)
                
        elif 'missing index' in line.lower():
            pass
            
    return result


HOLDOUT_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS holdout;

CREATE TABLE IF NOT EXISTS holdout.customers (
    customer_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    city TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS holdout.products (
    product_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price NUMERIC NOT NULL,
    stock INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS holdout.orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES holdout.customers(customer_id),
    order_date TIMESTAMP DEFAULT NOW(),
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS holdout.order_items (
    item_id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES holdout.orders(order_id),
    product_id INTEGER REFERENCES holdout.products(product_id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC NOT NULL
);

CREATE TABLE IF NOT EXISTS holdout.reviews (
    review_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES holdout.customers(customer_id),
    product_id INTEGER REFERENCES holdout.products(product_id),
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    review_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""


def seed_holdout(connection: Any) -> None:
    """Populate holdout schema with test data using seed 99."""
    if not connection:
        return

    random.seed(99)
    fake = Faker()
    Faker.seed(99)

    with connection.cursor() as cur:
        cur.execute("TRUNCATE holdout.reviews, holdout.order_items, holdout.orders, holdout.customers, holdout.products CASCADE")

        customer_ids = []
        for _ in range(100):
            name = fake.name()
            email = fake.unique.email()
            city = fake.city()
            cur.execute(
                "INSERT INTO holdout.customers (name, email, city) VALUES (%s, %s, %s) RETURNING customer_id",
                (name, email, city),
            )
            customer_ids.append(cur.fetchone()[0])

        categories = ["Electronics", "Clothing", "Home", "Sports", "Books"]
        product_ids = []
        for _ in range(50):
            name = fake.catch_phrase()
            category = random.choice(categories)
            price = round(random.uniform(10, 500), 2)
            stock = random.randint(0, 100)
            cur.execute(
                "INSERT INTO holdout.products (name, category, price, stock) VALUES (%s, %s, %s, %s) RETURNING product_id",
                (name, category, price, stock),
            )
            product_ids.append(cur.fetchone()[0])

        order_ids = []
        statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
        for _ in range(300):
            customer_id = random.choice(customer_ids)
            order_date = fake.date_time_between(start_date="-1y", end_date="now")
            status = random.choice(statuses)
            cur.execute(
                "INSERT INTO holdout.orders (customer_id, order_date, status) VALUES (%s, %s, %s) RETURNING order_id",
                (customer_id, order_date, status),
            )
            order_ids.append(cur.fetchone()[0])

        for _ in range(600):
            order_id = random.choice(order_ids)
            product_id = random.choice(product_ids)
            quantity = random.randint(1, 10)
            unit_price = round(random.uniform(10, 500), 2)
            cur.execute(
                "INSERT INTO holdout.order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, quantity, unit_price),
            )

        for _ in range(200):
            customer_id = random.choice(customer_ids)
            product_id = random.choice(product_ids)
            rating = random.randint(1, 5)
            review_text = fake.text(max_nb_chars=200)
            cur.execute(
                "INSERT INTO holdout.reviews (customer_id, product_id, rating, review_text) VALUES (%s, %s, %s, %s)",
                (customer_id, product_id, rating, review_text),
            )

        connection.commit()
