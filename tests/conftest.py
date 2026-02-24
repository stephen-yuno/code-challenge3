"""
Shared test fixtures for the Verdant Goods Chargeback Prevention API.

Provides:
- async test client (httpx.AsyncClient against the FastAPI app)
- test database setup/teardown (in-memory SQLite or temp file)
- sample transaction and chargeback data factories
"""
import os
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Force test database before importing app
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TESTING"] = "1"

from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------

def make_transaction(**overrides) -> Dict[str, Any]:
    """Build a sample transaction payload with sensible defaults."""
    base = {
        "transaction_id": "txn_test_001",
        "email": "legit.customer@gmail.com",
        "card_bin": "411111",
        "card_last_four": "1234",
        "amount": 120.00,
        "currency": "USD",
        "billing_country": "BR",
        "shipping_country": "BR",
        "ip_country": "BR",
        "product_category": "apparel",
        "customer_id": "cust_001",
        "is_first_purchase": False,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    base.update(overrides)
    return base


def make_low_risk_transaction(**overrides) -> Dict[str, Any]:
    """A clearly safe transaction that should score LOW."""
    defaults = dict(
        transaction_id="txn_low_risk",
        email="maria.silva@gmail.com",
        billing_country="BR",
        shipping_country="BR",
        ip_country="BR",
        product_category="apparel",
        amount=45.00,
        is_first_purchase=False,
    )
    defaults.update(overrides)
    return make_transaction(**defaults)


def make_high_risk_transaction(**overrides) -> Dict[str, Any]:
    """A clearly suspicious transaction that should score HIGH or CRITICAL."""
    defaults = dict(
        transaction_id="txn_high_risk",
        email="x7k9m2p@temp-mail.org",
        billing_country="BR",
        shipping_country="CO",
        ip_country="MX",
        product_category="electronics",
        amount=799.00,
        is_first_purchase=True,
    )
    defaults.update(overrides)
    return make_transaction(**defaults)


def make_chargeback(**overrides) -> Dict[str, Any]:
    """Build a sample chargeback record."""
    base = {
        "id": "cb_test_001",
        "transaction_id": "txn_cb_001",
        "transaction_date": "2025-11-15",
        "chargeback_date": "2026-01-10",
        "amount": 150.00,
        "currency": "USD",
        "country": "BR",
        "product_category": "electronics",
        "reason_code": "FRAUD",
        "email": "buyer@example.com",
        "card_bin": "411111",
    }
    base.update(overrides)
    return base


def make_chargebacks_dataset() -> List[Dict[str, Any]]:
    """
    Generate a controlled chargeback dataset with known patterns.
    Returns 20 records with clear distributions for testing analysis logic.
    """
    records = []

    # 10 from BR (50%), 6 from MX (30%), 4 from CO (20%)
    # Reason codes: 8 FRAUD, 5 NOT_RECEIVED, 4 NOT_AS_DESCRIBED, 2 DUPLICATE, 1 OTHER
    # Categories: 8 electronics, 7 apparel, 5 home_goods
    dataset = [
        # BR - FRAUD - electronics (high concentration)
        ("BR", "FRAUD", "electronics", 300.0, "fraud1@example.com", "510510", 30),
        ("BR", "FRAUD", "electronics", 450.0, "fraud1@example.com", "510510", 45),
        ("BR", "FRAUD", "electronics", 200.0, "fraud2@example.com", "510510", 60),
        ("BR", "FRAUD", "apparel", 80.0, "fraud3@example.com", "411111", 25),
        ("BR", "FRAUD", "home_goods", 150.0, "fraud4@example.com", "422222", 90),
        # BR - other reasons
        ("BR", "NOT_RECEIVED", "apparel", 55.0, "buyer1@example.com", "433333", 40),
        ("BR", "NOT_RECEIVED", "electronics", 320.0, "buyer2@example.com", "433333", 50),
        ("BR", "NOT_AS_DESCRIBED", "electronics", 275.0, "buyer3@example.com", "444444", 35),
        ("BR", "DUPLICATE", "apparel", 40.0, "buyer4@example.com", "455555", 22),
        ("BR", "OTHER", "home_goods", 60.0, "buyer5@example.com", "466666", 100),
        # MX
        ("MX", "FRAUD", "electronics", 500.0, "mxbuyer1@example.com", "520520", 55),
        ("MX", "FRAUD", "apparel", 120.0, "mxbuyer2@example.com", "520520", 38),
        ("MX", "NOT_RECEIVED", "home_goods", 90.0, "mxbuyer3@example.com", "533333", 70),
        ("MX", "NOT_AS_DESCRIBED", "apparel", 65.0, "mxbuyer4@example.com", "544444", 28),
        ("MX", "NOT_AS_DESCRIBED", "home_goods", 110.0, "mxbuyer5@example.com", "544444", 42),
        ("MX", "DUPLICATE", "electronics", 350.0, "mxbuyer6@example.com", "555555", 80),
        # CO
        ("CO", "FRAUD", "apparel", 95.0, "cobuyer1@example.com", "630630", 33),
        ("CO", "NOT_RECEIVED", "home_goods", 180.0, "cobuyer2@example.com", "633333", 48),
        ("CO", "NOT_RECEIVED", "electronics", 420.0, "cobuyer3@example.com", "633333", 65),
        ("CO", "NOT_AS_DESCRIBED", "apparel", 70.0, "cobuyer4@example.com", "644444", 105),
    ]

    base_txn_date = datetime(2025, 11, 1)
    for i, (country, reason, category, amount, email, card_bin, lag_days) in enumerate(dataset):
        txn_date = base_txn_date + timedelta(days=i * 3)
        cb_date = txn_date + timedelta(days=lag_days)
        records.append(make_chargeback(
            id=f"cb_{i+1:03d}",
            transaction_id=f"txn_cb_{i+1:03d}",
            transaction_date=txn_date.strftime("%Y-%m-%d"),
            chargeback_date=cb_date.strftime("%Y-%m-%d"),
            amount=amount,
            country=country,
            product_category=category,
            reason_code=reason,
            email=email,
            card_bin=card_bin,
        ))

    return records


# ---------------------------------------------------------------------------
# App / client fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Async test client that talks to the FastAPI app with a fresh in-memory DB.

    Each test gets an isolated database: we close any existing connection,
    then re-initialize the schema so tables exist in the new :memory: DB.
    """
    from app import database
    from app.main import app

    # Reset the connection so a fresh :memory: DB is created
    database.close_connection()
    database.init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    # Teardown: close connection so next test starts fresh
    database.close_connection()
