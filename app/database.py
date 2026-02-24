import json
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "verdant_goods.db"
SEED_DIR = Path(__file__).parent / "seed"

_connection: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
    return _connection


def close_connection() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def init_schema() -> None:
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            card_bin TEXT NOT NULL,
            card_last_four TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            billing_country TEXT NOT NULL,
            shipping_country TEXT NOT NULL,
            ip_country TEXT NOT NULL,
            product_category TEXT NOT NULL,
            customer_id TEXT,
            is_first_purchase INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chargebacks (
            id TEXT PRIMARY KEY,
            transaction_id TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            chargeback_date TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            country TEXT NOT NULL,
            product_category TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            email TEXT NOT NULL,
            card_bin TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            conditions TEXT NOT NULL,
            action TEXT NOT NULL,
            risk_score_modifier INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()


def load_seed_data() -> None:
    conn = get_connection()

    # Only seed if tables are empty
    row = conn.execute("SELECT COUNT(*) as cnt FROM transactions").fetchone()
    if row["cnt"] > 0:
        return

    txn_path = SEED_DIR / "transactions.json"
    cb_path = SEED_DIR / "chargebacks.json"

    if txn_path.exists():
        with open(txn_path) as f:
            transactions = json.load(f)
        for txn in transactions:
            conn.execute(
                """INSERT OR IGNORE INTO transactions
                   (id, email, card_bin, card_last_four, amount, currency,
                    billing_country, shipping_country, ip_country,
                    product_category, customer_id, is_first_purchase, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    txn["transaction_id"],
                    txn["email"],
                    txn["card_bin"],
                    txn["card_last_four"],
                    txn["amount"],
                    txn.get("currency", "USD"),
                    txn["billing_country"],
                    txn["shipping_country"],
                    txn["ip_country"],
                    txn["product_category"],
                    txn.get("customer_id"),
                    1 if txn.get("is_first_purchase", True) else 0,
                    txn["timestamp"],
                ),
            )

    if cb_path.exists():
        with open(cb_path) as f:
            chargebacks = json.load(f)
        for cb in chargebacks:
            conn.execute(
                """INSERT OR IGNORE INTO chargebacks
                   (id, transaction_id, transaction_date, chargeback_date,
                    amount, currency, country, product_category,
                    reason_code, email, card_bin)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cb["id"],
                    cb["transaction_id"],
                    cb["transaction_date"],
                    cb["chargeback_date"],
                    cb["amount"],
                    cb.get("currency", "USD"),
                    cb["country"],
                    cb["product_category"],
                    cb["reason_code"],
                    cb["email"],
                    cb["card_bin"],
                ),
            )

    conn.commit()


def seed_default_rules() -> None:
    """Seed default fraud rules if none exist."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM rules").fetchone()
    if row["cnt"] > 0:
        return

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    default_rules = [
        {
            "id": "rule_001",
            "name": "High-value first-time buyer",
            "description": "Flag any transaction over $500 from a first-time customer",
            "conditions": json.dumps([
                {"field": "amount", "operator": "gt", "value": 500},
                {"field": "is_first_purchase", "operator": "eq", "value": True},
            ]),
            "action": "MANUAL_REVIEW",
            "risk_score_modifier": 30,
            "is_active": 1,
            "priority": 1,
            "created_at": now,
        },
        {
            "id": "rule_002",
            "name": "Cross-border disposable email",
            "description": "Auto-reject cross-border transactions with disposable email",
            "conditions": json.dumps([
                {"field": "billing_country", "operator": "neq", "value_field": "shipping_country"},
                {"field": "email_domain_disposable", "operator": "eq", "value": True},
            ]),
            "action": "REJECT",
            "risk_score_modifier": 50,
            "is_active": 1,
            "priority": 2,
            "created_at": now,
        },
        {
            "id": "rule_003",
            "name": "High velocity electronics",
            "description": "Review electronics purchases from high-velocity accounts",
            "conditions": json.dumps([
                {"field": "product_category", "operator": "eq", "value": "electronics"},
                {"field": "velocity_24h", "operator": "gte", "value": 3},
            ]),
            "action": "MANUAL_REVIEW",
            "risk_score_modifier": 20,
            "is_active": 1,
            "priority": 3,
            "created_at": now,
        },
    ]

    for rule in default_rules:
        conn.execute(
            """INSERT OR IGNORE INTO rules
               (id, name, description, conditions, action,
                risk_score_modifier, is_active, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rule["id"],
                rule["name"],
                rule["description"],
                rule["conditions"],
                rule["action"],
                rule["risk_score_modifier"],
                rule["is_active"],
                rule["priority"],
                rule["created_at"],
            ),
        )
    conn.commit()


def init_db() -> None:
    """Initialize database: create schema, load seed data, seed rules."""
    init_schema()
    load_seed_data()
    seed_default_rules()
