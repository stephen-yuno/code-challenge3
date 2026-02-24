from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from app.database import get_connection
from app.models.transaction import RiskFactor, RiskScoreResponse, TransactionRequest
from app.services.disposable_emails import (
    compute_entropy_ratio,
    get_email_local_part,
    is_disposable_domain,
)

DEFAULT_AOV = 120.0


def _score_velocity(txn: TransactionRequest) -> Optional[RiskFactor]:
    """Signal 1: Velocity checks - transactions from same email/card_bin in last 24h."""
    conn = get_connection()
    cutoff = (txn.timestamp - timedelta(hours=24)).isoformat()
    ts = txn.timestamp.isoformat()

    email_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM transactions WHERE email = ? AND created_at > ? AND created_at <= ?",
        (txn.email, cutoff, ts),
    ).fetchone()["cnt"]

    card_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM transactions WHERE card_bin = ? AND created_at > ? AND created_at <= ?",
        (txn.card_bin, cutoff, ts),
    ).fetchone()["cnt"]

    max_count = max(email_count, card_count)

    if max_count <= 1:
        return None
    elif max_count <= 3:
        score = 5
    elif max_count <= 6:
        score = 15
    else:
        score = 25

    return RiskFactor(
        signal="velocity_check",
        score=score,
        description=f"{max_count} transactions from same email/card_bin in last 24h",
    )


def _score_geolocation(txn: TransactionRequest) -> Optional[RiskFactor]:
    """Signal 2: Geolocation mismatch - compare billing, shipping, IP countries."""
    mismatches = 0
    pairs = []
    if txn.billing_country != txn.shipping_country:
        mismatches += 1
        pairs.append("billing/shipping")
    if txn.billing_country != txn.ip_country:
        mismatches += 1
        pairs.append("billing/IP")
    if txn.shipping_country != txn.ip_country:
        mismatches += 1
        pairs.append("shipping/IP")

    if mismatches == 0:
        return None

    score = min(mismatches * 10, 20)
    return RiskFactor(
        signal="geolocation_mismatch",
        score=score,
        description=f"Country mismatch detected: {', '.join(pairs)}",
    )


def _score_category(txn: TransactionRequest) -> Optional[RiskFactor]:
    """Signal 3: High-risk product category."""
    scores = {"electronics": 15, "home_goods": 5, "apparel": 0}
    score = scores.get(txn.product_category, 0)
    if score == 0:
        return None
    return RiskFactor(
        signal="high_risk_category",
        score=score,
        description=f"Product category '{txn.product_category}' has elevated chargeback rates",
    )


def _score_amount_anomaly(txn: TransactionRequest) -> Optional[RiskFactor]:
    """Signal 4: Amount anomaly - compare to average order value."""
    conn = get_connection()
    row = conn.execute("SELECT AVG(amount) as avg_amount FROM transactions").fetchone()
    aov = row["avg_amount"] if row["avg_amount"] is not None else DEFAULT_AOV

    if aov <= 0:
        aov = DEFAULT_AOV

    ratio = txn.amount / aov

    if ratio <= 2.0:
        return None
    elif ratio <= 3.0:
        score = 8
    elif ratio <= 5.0:
        score = 14
    else:
        score = 20

    return RiskFactor(
        signal="amount_anomaly",
        score=score,
        description=f"Transaction amount (${txn.amount:.2f}) exceeds average order value by {ratio:.1f}x",
    )


def _score_new_customer(txn: TransactionRequest) -> Optional[RiskFactor]:
    """Signal 5: New customer risk."""
    if not txn.is_first_purchase:
        return None

    if txn.amount > 200:
        score = 10
        desc = "First-time customer with high-value purchase (>${:.2f})".format(txn.amount)
    else:
        score = 5
        desc = "First-time customer"

    return RiskFactor(
        signal="new_customer_risk",
        score=score,
        description=desc,
    )


def _score_email_patterns(txn: TransactionRequest) -> Optional[RiskFactor]:
    """Signal 6: Email/domain patterns."""
    if is_disposable_domain(txn.email):
        return RiskFactor(
            signal="email_pattern",
            score=10,
            description=f"Email uses known disposable domain",
        )

    local_part = get_email_local_part(txn.email)
    entropy = compute_entropy_ratio(local_part)
    if entropy > 0.85 and len(local_part) > 12:
        return RiskFactor(
            signal="email_pattern",
            score=5,
            description=f"Email local part appears randomly generated (entropy: {entropy:.2f})",
        )

    return None


def _map_risk_level(score: int) -> Tuple[str, str]:
    """Map numeric score to risk level and recommended action."""
    if score <= 25:
        return "LOW", "APPROVE"
    elif score <= 50:
        return "MEDIUM", "APPROVE"
    elif score <= 75:
        return "HIGH", "MANUAL_REVIEW"
    else:
        return "CRITICAL", "REJECT"


def score_transaction(txn: TransactionRequest) -> RiskScoreResponse:
    """Score a transaction using the 6-signal risk engine.

    The algorithm is deterministic: same inputs always produce the same score.
    """
    signal_funcs = [
        _score_velocity,
        _score_geolocation,
        _score_category,
        _score_amount_anomaly,
        _score_new_customer,
        _score_email_patterns,
    ]

    risk_factors = []
    total_score = 0

    for func in signal_funcs:
        factor = func(txn)
        if factor is not None:
            risk_factors.append(factor)
            total_score += factor.score

    # Apply rule engine adjustments
    from app.services.rule_engine import rule_engine

    txn_data = {
        "transaction_id": txn.transaction_id,
        "email": txn.email,
        "card_bin": txn.card_bin,
        "card_last_four": txn.card_last_four,
        "amount": txn.amount,
        "currency": txn.currency,
        "billing_country": txn.billing_country,
        "shipping_country": txn.shipping_country,
        "ip_country": txn.ip_country,
        "product_category": txn.product_category,
        "customer_id": txn.customer_id,
        "is_first_purchase": txn.is_first_purchase,
        "timestamp": txn.timestamp,
    }
    modifier, action_override = rule_engine.evaluate_all_rules(txn_data)
    total_score += modifier
    total_score = min(max(total_score, 0), 100)

    risk_level, action = _map_risk_level(total_score)
    if action_override is not None:
        action = action_override

    # Insert this transaction into DB for future velocity checks
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO transactions
           (id, email, card_bin, card_last_four, amount, currency,
            billing_country, shipping_country, ip_country,
            product_category, customer_id, is_first_purchase, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            txn.transaction_id,
            txn.email,
            txn.card_bin,
            txn.card_last_four,
            txn.amount,
            txn.currency,
            txn.billing_country,
            txn.shipping_country,
            txn.ip_country,
            txn.product_category,
            txn.customer_id,
            1 if txn.is_first_purchase else 0,
            txn.timestamp.isoformat(),
        ),
    )
    conn.commit()

    return RiskScoreResponse(
        transaction_id=txn.transaction_id,
        risk_score=total_score,
        risk_level=risk_level,
        recommended_action=action,
        risk_factors=risk_factors,
        scored_at=datetime.now(timezone.utc),
    )


def get_velocity_count(email: str, timestamp: datetime) -> int:
    """Get the 24h velocity count for an email. Used by rule engine."""
    conn = get_connection()
    cutoff = (timestamp - timedelta(hours=24)).isoformat()
    ts = timestamp.isoformat()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM transactions WHERE email = ? AND created_at > ? AND created_at <= ?",
        (email, cutoff, ts),
    ).fetchone()
    return row["cnt"]
