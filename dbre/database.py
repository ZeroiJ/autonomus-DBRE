from __future__ import annotations

import os
import random
from typing import Optional

import psycopg2
from faker import Faker


class ConnectionError(Exception):
    pass


class DBREPostgres:

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[str] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.host = host or os.getenv("DB_HOST", "localhost")
        self.port = port or os.getenv("DB_PORT", "5432")
        self.database = database or os.getenv("DB_NAME", "dbre")
        self.user = user or os.getenv("DB_USER", "postgres")
        self.password = password or os.getenv("DB_PASSWORD", "postgres")
        self.conn = None
        self.fake = Faker()

    def connect(self) -> None:
        try:
            self.conn = psycopg2.connect(
                host=self.host, port=self.port, database=self.database,
                user=self.user, password=self.password
            )
            self.conn.autocommit = False
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to connect: {e}")

    def create_tables(self) -> None:
        if not self.conn:
            self.connect()
        try:
            cur = self.conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id SERIAL PRIMARY KEY, name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL, city TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id SERIAL PRIMARY KEY, name TEXT NOT NULL,
                    category TEXT NOT NULL, price NUMERIC NOT NULL,
                    stock INTEGER DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id SERIAL PRIMARY KEY,
                    customer_id INTEGER REFERENCES customers(customer_id),
                    order_date TIMESTAMP DEFAULT NOW(),
                    status TEXT DEFAULT 'pending'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    item_id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(order_id),
                    product_id INTEGER REFERENCES products(product_id),
                    quantity INTEGER NOT NULL,
                    unit_price NUMERIC NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id SERIAL PRIMARY KEY,
                    customer_id INTEGER REFERENCES customers(customer_id),
                    product_id INTEGER REFERENCES products(product_id),
                    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
                    review_text TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            self.conn.commit()
            cur.close()
        except psycopg2.Error as e:
            self.conn.rollback()
            raise ConnectionError(f"Failed to create tables: {e}")

    def seed_data(self) -> None:
        """Seed the database with realistic test data. Drops and rebuilds schema first."""
        if not self.conn:
            self.connect()
        random.seed(42)
        Faker.seed(42)
        try:
            cur = self.conn.cursor()
            cur.execute("DROP TABLE IF EXISTS reviews, order_items, orders, products, customers CASCADE;")
            self.conn.commit()
            cur.close()
        except Exception:
            self.conn.rollback()
        
        self.create_tables()
        
        try:
            cur = self.conn.cursor()
            customer_ids = []
            for _ in range(100):
                name = self.fake.name()
                email = self.fake.unique.email()
                city = self.fake.city()
                cur.execute(
                    "INSERT INTO customers (name, email, city) VALUES (%s, %s, %s) RETURNING customer_id",
                    (name, email, city),
                )
                customer_ids.append(cur.fetchone()[0])

            categories = ["Electronics", "Clothing", "Home", "Sports", "Books"]
            product_ids = []
            for _ in range(50):
                name = self.fake.catch_phrase()
                category = random.choice(categories)
                price = round(random.uniform(10, 500), 2)
                stock = random.randint(0, 100)
                cur.execute(
                    "INSERT INTO products (name, category, price, stock) VALUES (%s, %s, %s, %s) RETURNING product_id",
                    (name, category, price, stock),
                )
                product_ids.append(cur.fetchone()[0])

            order_ids = []
            statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
            for _ in range(300):
                customer_id = random.choice(customer_ids)
                order_date = self.fake.date_time_between(start_date="-1y", end_date="now")
                status = random.choice(statuses)
                cur.execute(
                    "INSERT INTO orders (customer_id, order_date, status) VALUES (%s, %s, %s) RETURNING order_id",
                    (customer_id, order_date, status),
                )
                order_ids.append(cur.fetchone()[0])

            for _ in range(600):
                order_id = random.choice(order_ids)
                product_id = random.choice(product_ids)
                quantity = random.randint(1, 10)
                unit_price = round(random.uniform(10, 500), 2)
                cur.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                    (order_id, product_id, quantity, unit_price),
                )

            for _ in range(200):
                customer_id = random.choice(customer_ids)
                product_id = random.choice(product_ids)
                rating = random.randint(1, 5)
                review_text = self.fake.text(max_nb_chars=200)
                cur.execute(
                    "INSERT INTO reviews (customer_id, product_id, rating, review_text) VALUES (%s, %s, %s, %s)",
                    (customer_id, product_id, rating, review_text),
                )

            self.conn.commit()
            cur.close()
        except psycopg2.Error as e:
            self.conn.rollback()
            raise ConnectionError(f"Failed to seed data: {e}")
