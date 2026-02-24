"""Generate deterministic test data for Verdant Goods Chargeback Prevention API.

Uses random.seed(42) for reproducibility. Generates:
- 60+ transactions with planted suspicious and clean patterns
- 250+ chargebacks with clear geographic, category, and repeat offender patterns
"""
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

OUTPUT_DIR = Path(__file__).parent

# Constants
COUNTRIES = ["BR", "MX", "CO"]
CATEGORIES = ["electronics", "apparel", "home_goods"]
REASON_CODES = ["FRAUD", "NOT_RECEIVED", "NOT_AS_DESCRIBED", "DUPLICATE", "OTHER"]
DISPOSABLE_DOMAINS = ["temp-mail.org", "guerrillamail.com", "mailinator.com", "throwaway.email", "yopmail.com"]
NORMAL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "hotmail.com", "protonmail.com"]

FIRST_NAMES = [
    "maria", "joao", "carlos", "ana", "pedro", "lucia", "miguel", "sofia",
    "diego", "valentina", "gabriel", "camila", "rafael", "isabella", "lucas",
    "fernanda", "mateo", "daniela", "andres", "paula", "santiago", "catalina",
    "jose", "mariana", "luis", "elena", "ricardo", "natalia", "jorge", "andrea",
]

LAST_NAMES = [
    "silva", "santos", "oliveira", "souza", "rodrigues", "ferreira", "alves",
    "pereira", "lima", "gomes", "costa", "ribeiro", "martins", "carvalho",
    "garcia", "lopez", "martinez", "hernandez", "gonzalez", "torres",
]

CARD_BINS = [
    "411111", "510510", "340000", "370000", "601100",
    "424242", "555555", "378282", "650000", "402400",
]

BASE_DATE = datetime(2026, 2, 20, 12, 0, 0)


def _gen_email(first: str, last: str, domain: str) -> str:
    return f"{first}.{last}@{domain}"


def _gen_txn_id() -> str:
    return f"txn_{uuid.uuid4().hex[:12]}"


def _gen_cb_id() -> str:
    return f"cb_{uuid.uuid4().hex[:12]}"


def _random_amount(mean: float = 120.0, std: float = 60.0, low: float = 15.0, high: float = 850.0) -> float:
    amt = random.gauss(mean, std)
    return round(max(low, min(high, amt)), 2)


def generate_transactions():
    transactions = []

    # === CLEAN PATTERNS (10-12 transactions) ===

    # Loyal repeat customer - same email, same country, moderate amounts
    loyal_email = "maria.silva@gmail.com"
    for i in range(4):
        transactions.append({
            "transaction_id": _gen_txn_id(),
            "email": loyal_email,
            "card_bin": "411111",
            "card_last_four": "4242",
            "amount": _random_amount(mean=80, std=20, low=30, high=150),
            "currency": "USD",
            "billing_country": "BR",
            "shipping_country": "BR",
            "ip_country": "BR",
            "product_category": random.choice(["apparel", "home_goods"]),
            "customer_id": "cust_loyal_001",
            "is_first_purchase": False,
            "timestamp": (BASE_DATE - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))).isoformat() + "Z",
        })

    # Local match - all geo fields identical, reasonable amount
    for i in range(4):
        country = random.choice(COUNTRIES)
        transactions.append({
            "transaction_id": _gen_txn_id(),
            "email": _gen_email(random.choice(FIRST_NAMES), random.choice(LAST_NAMES), random.choice(NORMAL_DOMAINS)),
            "card_bin": random.choice(CARD_BINS),
            "card_last_four": f"{random.randint(1000, 9999)}",
            "amount": _random_amount(mean=90, std=30, low=20, high=200),
            "currency": "USD",
            "billing_country": country,
            "shipping_country": country,
            "ip_country": country,
            "product_category": random.choice(CATEGORIES),
            "customer_id": f"cust_{uuid.uuid4().hex[:8]}",
            "is_first_purchase": False,
            "timestamp": (BASE_DATE - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))).isoformat() + "Z",
        })

    # Small apparel purchases - low amount, repeat buyer, same country
    for i in range(4):
        country = random.choice(COUNTRIES)
        transactions.append({
            "transaction_id": _gen_txn_id(),
            "email": _gen_email(random.choice(FIRST_NAMES), random.choice(LAST_NAMES), random.choice(NORMAL_DOMAINS)),
            "card_bin": random.choice(CARD_BINS),
            "card_last_four": f"{random.randint(1000, 9999)}",
            "amount": _random_amount(mean=35, std=10, low=15, high=60),
            "currency": "USD",
            "billing_country": country,
            "shipping_country": country,
            "ip_country": country,
            "product_category": "apparel",
            "customer_id": f"cust_{uuid.uuid4().hex[:8]}",
            "is_first_purchase": False,
            "timestamp": (BASE_DATE - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))).isoformat() + "Z",
        })

    # === SUSPICIOUS PATTERNS (10-12 transactions) ===

    # 1. Velocity abuse: 12 records with same email within a few hours
    #    (challenge explicitly requires "Same email making 10+ transactions in 24 hours")
    velocity_base = BASE_DATE - timedelta(hours=4)
    for i in range(12):
        transactions.append({
            "transaction_id": _gen_txn_id(),
            "email": "speed_buyer@temp-mail.org",
            "card_bin": "510510",
            "card_last_four": "9999",
            "amount": _random_amount(mean=200, std=50, low=100, high=400),
            "currency": "USD",
            "billing_country": "BR",
            "shipping_country": "BR",
            "ip_country": "BR",
            "product_category": "electronics",
            "customer_id": "cust_speed",
            "is_first_purchase": False,
            "timestamp": (velocity_base + timedelta(minutes=i * 10)).isoformat() + "Z",
        })

    # 2. Geo mismatch: 3 records where billing=BR, shipping=CO, IP=MX
    for i in range(3):
        transactions.append({
            "transaction_id": _gen_txn_id(),
            "email": _gen_email(random.choice(FIRST_NAMES), random.choice(LAST_NAMES), random.choice(NORMAL_DOMAINS)),
            "card_bin": random.choice(CARD_BINS),
            "card_last_four": f"{random.randint(1000, 9999)}",
            "amount": _random_amount(mean=250, std=80, low=100, high=500),
            "currency": "USD",
            "billing_country": "BR",
            "shipping_country": "CO",
            "ip_country": "MX",
            "product_category": random.choice(CATEGORIES),
            "customer_id": f"cust_{uuid.uuid4().hex[:8]}",
            "is_first_purchase": random.choice([True, False]),
            "timestamp": (BASE_DATE - timedelta(days=random.randint(1, 15), hours=random.randint(0, 23))).isoformat() + "Z",
        })

    # 3. High-value new customer: 2 records with first-time buyers spending $600+
    for i in range(2):
        transactions.append({
            "transaction_id": _gen_txn_id(),
            "email": _gen_email(random.choice(FIRST_NAMES), random.choice(LAST_NAMES), random.choice(NORMAL_DOMAINS)),
            "card_bin": random.choice(CARD_BINS),
            "card_last_four": f"{random.randint(1000, 9999)}",
            "amount": _random_amount(mean=700, std=50, low=600, high=850),
            "currency": "USD",
            "billing_country": random.choice(COUNTRIES),
            "shipping_country": random.choice(COUNTRIES),
            "ip_country": random.choice(COUNTRIES),
            "product_category": "electronics",
            "customer_id": None,
            "is_first_purchase": True,
            "timestamp": (BASE_DATE - timedelta(days=random.randint(1, 10), hours=random.randint(0, 23))).isoformat() + "Z",
        })

    # 4. Disposable emails: 3 records using disposable domains
    for i in range(3):
        domain = random.choice(DISPOSABLE_DOMAINS)
        country = random.choice(COUNTRIES)
        transactions.append({
            "transaction_id": _gen_txn_id(),
            "email": f"buyer{random.randint(100,999)}@{domain}",
            "card_bin": random.choice(CARD_BINS),
            "card_last_four": f"{random.randint(1000, 9999)}",
            "amount": _random_amount(mean=180, std=60, low=50, high=400),
            "currency": "USD",
            "billing_country": country,
            "shipping_country": country,
            "ip_country": country,
            "product_category": random.choice(CATEGORIES),
            "customer_id": f"cust_{uuid.uuid4().hex[:8]}",
            "is_first_purchase": random.choice([True, False]),
            "timestamp": (BASE_DATE - timedelta(days=random.randint(1, 20), hours=random.randint(0, 23))).isoformat() + "Z",
        })

    # 5. Combined red flags: velocity + geo mismatch + disposable email
    combo_base = BASE_DATE - timedelta(hours=1)
    transactions.append({
        "transaction_id": _gen_txn_id(),
        "email": "xk7q9m2p@guerrillamail.com",
        "card_bin": "510510",
        "card_last_four": "0001",
        "amount": 749.99,
        "currency": "USD",
        "billing_country": "BR",
        "shipping_country": "MX",
        "ip_country": "CO",
        "product_category": "electronics",
        "customer_id": None,
        "is_first_purchase": True,
        "timestamp": combo_base.isoformat() + "Z",
    })

    # === GENERAL TRANSACTIONS to reach 60+ ===
    country_weights = [0.40, 0.35, 0.25]  # BR, MX, CO
    cat_weights = [0.30, 0.40, 0.30]  # electronics, apparel, home_goods

    while len(transactions) < 74:
        country = random.choices(COUNTRIES, weights=country_weights)[0]
        category = random.choices(CATEGORIES, weights=cat_weights)[0]
        is_first = random.random() < 0.4
        # Sometimes mismatch geo for variety
        if random.random() < 0.15:
            ship_country = random.choice([c for c in COUNTRIES if c != country])
        else:
            ship_country = country
        ip_country = country if random.random() > 0.1 else random.choice(COUNTRIES)

        transactions.append({
            "transaction_id": _gen_txn_id(),
            "email": _gen_email(random.choice(FIRST_NAMES), random.choice(LAST_NAMES), random.choice(NORMAL_DOMAINS)),
            "card_bin": random.choice(CARD_BINS),
            "card_last_four": f"{random.randint(1000, 9999)}",
            "amount": _random_amount(),
            "currency": "USD",
            "billing_country": country,
            "shipping_country": ship_country,
            "ip_country": ip_country,
            "product_category": category,
            "customer_id": f"cust_{uuid.uuid4().hex[:8]}",
            "is_first_purchase": is_first,
            "timestamp": (BASE_DATE - timedelta(days=random.randint(0, 45), hours=random.randint(0, 23))).isoformat() + "Z",
        })

    return transactions


def generate_chargebacks():
    chargebacks = []

    # Distribution targets:
    # Countries: 55% BR, 25% MX, 20% CO
    # Categories: 45% electronics, 30% apparel, 25% home_goods
    # Reason codes: 40% FRAUD, 25% NOT_RECEIVED, 20% NOT_AS_DESCRIBED, 10% DUPLICATE, 5% OTHER

    country_weights = [0.55, 0.25, 0.20]
    cat_weights = [0.45, 0.30, 0.25]
    reason_weights = [0.40, 0.25, 0.20, 0.10, 0.05]

    # Repeat offender emails (3 emails with 4-6 chargebacks each)
    repeat_emails = [
        "suspicious_buyer@temp-mail.org",
        "fraud_master@guerrillamail.com",
        "repeat_offender@mailinator.com",
    ]

    # Repeat card BINs (2 BINs with 5-8 chargebacks each)
    repeat_bins = ["510510", "340000"]

    # Helper to generate a chargeback
    def _make_chargeback(
        country=None, category=None, reason=None, email=None,
        card_bin=None, days_lag=None, txn_date=None,
    ):
        if country is None:
            country = random.choices(COUNTRIES, weights=country_weights)[0]
        if category is None:
            category = random.choices(CATEGORIES, weights=cat_weights)[0]
        if reason is None:
            # Brazil FRAUD concentration: 70% of FRAUD from BR
            if country == "BR" and random.random() < 0.45:
                reason = "FRAUD"
            else:
                reason = random.choices(REASON_CODES, weights=reason_weights)[0]
        if email is None:
            email = _gen_email(random.choice(FIRST_NAMES), random.choice(LAST_NAMES), random.choice(NORMAL_DOMAINS))
        if card_bin is None:
            card_bin = random.choice(CARD_BINS)
        if txn_date is None:
            txn_date = BASE_DATE - timedelta(days=random.randint(40, 150))
        if days_lag is None:
            days_lag = int(max(18, min(120, random.gauss(47, 20))))

        cb_date = txn_date + timedelta(days=days_lag)
        amount = _random_amount(mean=180, std=80, low=25, high=600)

        # Electronics NOT_AS_DESCRIBED: 3x rate
        if category == "electronics" and random.random() < 0.25:
            reason = "NOT_AS_DESCRIBED"

        return {
            "id": _gen_cb_id(),
            "transaction_id": _gen_txn_id(),
            "transaction_date": txn_date.strftime("%Y-%m-%d"),
            "chargeback_date": cb_date.strftime("%Y-%m-%d"),
            "amount": amount,
            "currency": "USD",
            "country": country,
            "product_category": category,
            "reason_code": reason,
            "email": email,
            "card_bin": card_bin,
        }

    # 1. Repeat offender emails (4-6 each)
    for email in repeat_emails:
        count = random.randint(4, 6)
        for _ in range(count):
            chargebacks.append(_make_chargeback(email=email, country="BR", reason="FRAUD"))

    # 2. Repeat card BINs (5-8 each)
    for card_bin in repeat_bins:
        count = random.randint(5, 8)
        for _ in range(count):
            chargebacks.append(_make_chargeback(card_bin=card_bin))

    # 3. Seasonal spike: December transactions have 2x chargebacks
    for _ in range(20):
        dec_date = datetime(2025, 12, random.randint(1, 28), random.randint(0, 23))
        chargebacks.append(_make_chargeback(txn_date=dec_date))

    # 4. General chargebacks to reach 250+
    while len(chargebacks) < 260:
        chargebacks.append(_make_chargeback())

    return chargebacks


def main():
    transactions = generate_transactions()
    chargebacks = generate_chargebacks()

    txn_path = OUTPUT_DIR / "transactions.json"
    cb_path = OUTPUT_DIR / "chargebacks.json"

    with open(txn_path, "w") as f:
        json.dump(transactions, f, indent=2)

    with open(cb_path, "w") as f:
        json.dump(chargebacks, f, indent=2)

    print(f"Generated {len(transactions)} transactions -> {txn_path}")
    print(f"Generated {len(chargebacks)} chargebacks -> {cb_path}")

    # Print some stats
    countries = {}
    for cb in chargebacks:
        countries[cb["country"]] = countries.get(cb["country"], 0) + 1
    print(f"\nChargeback country distribution:")
    for c, n in sorted(countries.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n} ({n/len(chargebacks)*100:.1f}%)")

    reasons = {}
    for cb in chargebacks:
        reasons[cb["reason_code"]] = reasons.get(cb["reason_code"], 0) + 1
    print(f"\nReason code distribution:")
    for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {r}: {n} ({n/len(chargebacks)*100:.1f}%)")


if __name__ == "__main__":
    main()
