"""
projects/p1_customer_support/src/database.py
SQLite database setup and seeding for Project 1.

Creates four tables from architecture.md:
- customers
- orders
- refunds
- escalations

Run directly to create and seed the database:
    python projects/p1_customer_support/src/database.py
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from agent_platform.logging import get_logger, log_event

# Get logger for this module
logger = get_logger(__name__)

# Database file lives in the data folder
DB_PATH = Path(__file__).parent.parent / "data" / "support.db"


def get_connection() -> sqlite3.Connection:
    """
    Get a connection to the SQLite database.
    Creates the database file if it doesn't exist.
    
    Returns:
        sqlite3.Connection with row_factory set so rows
        behave like dictionaries — access by column name
        instead of index number
    """
    conn = sqlite3.connect(DB_PATH)
    
    # row_factory lets you access columns by name
    # instead of index: row["email"] instead of row[1]
    conn.row_factory = sqlite3.Row
    
    # Enable foreign key enforcement
    # SQLite doesn't enforce foreign keys by default
    conn.execute("PRAGMA foreign_keys = ON")
    
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """
    Create all four tables from architecture.md schema.
    Uses IF NOT EXISTS so safe to run multiple times.
    """
    conn.executescript("""
        -- Customers table
        -- Stores verified customer information
        CREATE TABLE IF NOT EXISTS customers (
            customer_id   TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            full_name     TEXT NOT NULL,
            account_status TEXT NOT NULL DEFAULT 'active',
            customer_tier  TEXT NOT NULL DEFAULT 'standard',
            created_at    TEXT NOT NULL
        );

        -- Orders table
        -- Each order belongs to one customer
        CREATE TABLE IF NOT EXISTS orders (
            order_id        TEXT PRIMARY KEY,
            customer_id     TEXT NOT NULL,
            order_number    TEXT UNIQUE NOT NULL,
            items           TEXT NOT NULL,
            order_date      TEXT NOT NULL,
            delivery_date   TEXT,
            order_status    TEXT NOT NULL DEFAULT 'delivered',
            total_amount    REAL NOT NULL,
            already_refunded INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        -- Refunds table
        -- Tracks all refund attempts and outcomes
        CREATE TABLE IF NOT EXISTS refunds (
            refund_id           TEXT PRIMARY KEY,
            order_id            TEXT NOT NULL,
            customer_id         TEXT NOT NULL,
            refund_amount       REAL NOT NULL,
            reason              TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'pending',
            confirmation_number TEXT,
            created_at          TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        -- Escalations table
        -- Tracks all human escalations
        CREATE TABLE IF NOT EXISTS escalations (
            escalation_id        TEXT PRIMARY KEY,
            customer_id          TEXT,
            order_id             TEXT,
            reason               TEXT NOT NULL,
            conversation_summary TEXT NOT NULL,
            recommended_action   TEXT NOT NULL,
            status               TEXT NOT NULL DEFAULT 'open',
            created_at           TEXT NOT NULL
        );
    """)
    
    conn.commit()
    log_event(logger, "tables_created", db_path=str(DB_PATH))


def seed_data(conn: sqlite3.Connection) -> None:
    """
    Seed the database with synthetic test data.
    
    Creates:
    - 5 customers (mix of standard/VIP, active/suspended)
    - 8 orders (various statuses and amounts)
    
    This gives us enough data to test all scenarios
    from our architecture document.
    """
    now = datetime.now()
    
    # ── CUSTOMERS ──────────────────────────────────────────
    # Mix of tiers and statuses to test all scenarios
    customers = [
        {
            "customer_id": "CUST-001",
            "email": "john.smith@email.com",
            "full_name": "John Smith",
            "account_status": "active",
            "customer_tier": "standard",
            "created_at": (now - timedelta(days=365)).isoformat(),
        },
        {
            "customer_id": "CUST-002",
            "email": "sarah.jones@email.com",
            "full_name": "Sarah Jones",
            "account_status": "active",
            "customer_tier": "vip",
            "created_at": (now - timedelta(days=730)).isoformat(),
        },
        {
            "customer_id": "CUST-003",
            "email": "mike.wilson@email.com",
            "full_name": "Mike Wilson",
            "account_status": "suspended",
            "customer_tier": "standard",
            "created_at": (now - timedelta(days=180)).isoformat(),
        },
        {
            "customer_id": "CUST-004",
            "email": "lisa.chen@email.com",
            "full_name": "Lisa Chen",
            "account_status": "active",
            "customer_tier": "vip",
            "created_at": (now - timedelta(days=500)).isoformat(),
        },
        {
            "customer_id": "CUST-005",
            "email": "bob.taylor@email.com",
            "full_name": "Bob Taylor",
            "account_status": "active",
            "customer_tier": "standard",
            "created_at": (now - timedelta(days=90)).isoformat(),
        },
    ]
    
    # ── ORDERS ─────────────────────────────────────────────
    # Mix of amounts to test the $500 hook
    # Some already refunded to test that error case
    orders = [
        {
            "order_id": "ORD-001",
            "customer_id": "CUST-001",
            "order_number": "#10001",
            "items": json.dumps([{"name": "Laptop Stand", "qty": 1, "price": 45.99}]),
            "order_date": (now - timedelta(days=30)).isoformat(),
            "delivery_date": (now - timedelta(days=25)).isoformat(),
            "order_status": "delivered",
            "total_amount": 45.99,
            "already_refunded": 0,
        },
        {
            "order_id": "ORD-002",
            "customer_id": "CUST-001",
            "order_number": "#10002",
            "items": json.dumps([{"name": "Mechanical Keyboard", "qty": 1, "price": 189.99}]),
            "order_date": (now - timedelta(days=60)).isoformat(),
            "delivery_date": (now - timedelta(days=55)).isoformat(),
            "order_status": "delivered",
            "total_amount": 189.99,
            "already_refunded": 0,
        },
        {
            "order_id": "ORD-003",
            "customer_id": "CUST-002",
            "order_number": "#10003",
            "items": json.dumps([{"name": "4K Monitor", "qty": 1, "price": 749.99}]),
            "order_date": (now - timedelta(days=14)).isoformat(),
            "delivery_date": (now - timedelta(days=10)).isoformat(),
            "order_status": "delivered",
            "total_amount": 749.99,
            "already_refunded": 0,
        },
        {
            "order_id": "ORD-004",
            "customer_id": "CUST-002",
            "order_number": "#10004",
            "items": json.dumps([{"name": "USB Hub", "qty": 2, "price": 29.99}]),
            "order_date": (now - timedelta(days=45)).isoformat(),
            "delivery_date": (now - timedelta(days=40)).isoformat(),
            "order_status": "delivered",
            "total_amount": 59.98,
            "already_refunded": 1,  # already refunded — tests that error case
        },
        {
            "order_id": "ORD-005",
            "customer_id": "CUST-004",
            "order_number": "#10005",
            "items": json.dumps([{"name": "Webcam Pro", "qty": 1, "price": 299.99}]),
            "order_date": (now - timedelta(days=7)).isoformat(),
            "delivery_date": (now - timedelta(days=3)).isoformat(),
            "order_status": "delivered",
            "total_amount": 299.99,
            "already_refunded": 0,
        },
        {
            "order_id": "ORD-006",
            "customer_id": "CUST-004",
            "order_number": "#10006",
            "items": json.dumps([{"name": "Ergonomic Chair", "qty": 1, "price": 599.99}]),
            "order_date": (now - timedelta(days=20)).isoformat(),
            "delivery_date": (now - timedelta(days=15)).isoformat(),
            "order_status": "delivered",
            "total_amount": 599.99,
            "already_refunded": 0,  # over $500 — tests hook
        },
        {
            "order_id": "ORD-007",
            "customer_id": "CUST-005",
            "order_number": "#10007",
            "items": json.dumps([{"name": "Mouse Pad XL", "qty": 1, "price": 24.99}]),
            "order_date": (now - timedelta(days=5)).isoformat(),
            "delivery_date": None,
            "order_status": "processing",  # not delivered — tests eligibility
            "total_amount": 24.99,
            "already_refunded": 0,
        },
        {
            "order_id": "ORD-008",
            "customer_id": "CUST-005",
            "order_number": "#10008",
            "items": json.dumps([{"name": "Cable Management Kit", "qty": 3, "price": 12.99}]),
            "order_date": (now - timedelta(days=10)).isoformat(),
            "delivery_date": (now - timedelta(days=6)).isoformat(),
            "order_status": "delivered",
            "total_amount": 38.97,
            "already_refunded": 0,
        },
    ]
    
    # Insert customers — ignore if already exists
    for customer in customers:
        conn.execute("""
            INSERT OR IGNORE INTO customers
            (customer_id, email, full_name, account_status, customer_tier, created_at)
            VALUES (:customer_id, :email, :full_name, :account_status, :customer_tier, :created_at)
        """, customer)
    
    # Insert orders — ignore if already exists
    for order in orders:
        conn.execute("""
            INSERT OR IGNORE INTO orders
            (order_id, customer_id, order_number, items, order_date, 
             delivery_date, order_status, total_amount, already_refunded)
            VALUES (:order_id, :customer_id, :order_number, :items, :order_date,
                    :delivery_date, :order_status, :total_amount, :already_refunded)
        """, order)
    
    conn.commit()
    
    log_event(logger, "data_seeded",
        customers=len(customers),
        orders=len(orders)
    )


def verify_data(conn: sqlite3.Connection) -> None:
    """
    Print a summary of what's in the database.
    Run after seeding to verify everything looks right.
    """
    customer_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    
    print("\n" + "="*50)
    print("DATABASE SUMMARY")
    print("="*50)
    print(f"Customers: {customer_count}")
    print(f"Orders:    {order_count}")
    print("\nCustomers:")
    
    for row in conn.execute("SELECT email, full_name, account_status, customer_tier FROM customers"):
        print(f"  {row['email']:<30} {row['full_name']:<20} {row['account_status']:<10} {row['customer_tier']}")
    
    print("\nOrders:")
    for row in conn.execute("""
        SELECT o.order_number, c.full_name, o.total_amount, 
               o.order_status, o.already_refunded
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        ORDER BY o.order_number
    """):
        refunded = "ALREADY REFUNDED" if row['already_refunded'] else ""
        over_500 = "OVER $500" if row['total_amount'] > 500 else ""
        print(f"  {row['order_number']}  {row['full_name']:<20} ${row['total_amount']:<8.2f} {row['order_status']:<12} {refunded} {over_500}")
    
    print("="*50 + "\n")


if __name__ == "__main__":
    """
    Run this file directly to create and seed the database.
    python projects/p1_customer_support/src/database.py
    """
    print(f"Creating database at: {DB_PATH}")
    
    conn = get_connection()
    create_tables(conn)
    seed_data(conn)
    verify_data(conn)
    conn.close()
    
    print("Database ready.")