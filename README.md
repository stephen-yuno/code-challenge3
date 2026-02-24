# Verdant Goods Chargeback Prevention API

A backend service for real-time fraud risk scoring and chargeback pattern analysis, built for Verdant Goods' e-commerce operations across Brazil, Mexico, and Colombia.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate test data (50+ transactions, 260+ chargebacks)
python -m app.seed.generate_data

# Start the server
uvicorn app.main:app --port 8000
```

Or use the quick-start script:

```bash
./run.sh
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## API Endpoints

### Health Check

```
GET /health
```

Returns `{"status": "healthy"}`.

### Risk Scoring (Requirement 1)

**Score a single transaction:**

```
POST /api/v1/transactions/score
```

```bash
curl -s -X POST http://localhost:8000/api/v1/transactions/score \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_001",
    "email": "buyer@temp-mail.org",
    "card_bin": "411111",
    "card_last_four": "1234",
    "amount": 750.00,
    "currency": "USD",
    "billing_country": "BR",
    "shipping_country": "CO",
    "ip_country": "MX",
    "product_category": "electronics",
    "is_first_purchase": true
  }'
```

**Response:**

```json
{
  "transaction_id": "txn_001",
  "risk_score": 100,
  "risk_level": "CRITICAL",
  "recommended_action": "REJECT",
  "risk_factors": [
    {"signal": "geolocation_mismatch", "score": 20, "description": "Country mismatch detected: billing/shipping, billing/IP, shipping/IP"},
    {"signal": "high_risk_category", "score": 15, "description": "Product category 'electronics' has elevated chargeback rates"},
    {"signal": "amount_anomaly", "score": 14, "description": "Transaction amount ($750.00) exceeds average order value by 4.8x"},
    {"signal": "new_customer_risk", "score": 10, "description": "First-time customer with high-value purchase (>$750.00)"},
    {"signal": "email_pattern", "score": 10, "description": "Email uses known disposable domain"}
  ],
  "scored_at": "2026-02-24T20:58:18Z"
}
```

The scoring engine evaluates 6 independent risk signals:

| Signal | Max Points | Description |
|--------|-----------|-------------|
| Velocity checks | 25 | Transactions from same email/card in last 24h |
| Geolocation mismatch | 20 | Billing, shipping, IP country mismatches |
| High-risk category | 15 | Electronics (15), home goods (5), apparel (0) |
| Amount anomaly | 20 | Compared to average order value |
| New customer risk | 10 | First-time buyer with high-value purchase |
| Email patterns | 10 | Disposable domains or random-looking addresses |

**Risk levels:** LOW (0-25) -> APPROVE, MEDIUM (26-50) -> APPROVE, HIGH (51-75) -> MANUAL_REVIEW, CRITICAL (76-100) -> REJECT

### Chargeback Analysis (Requirement 2)

```
GET /api/v1/chargebacks/analysis
GET /api/v1/chargebacks/analysis?start_date=2025-11-01&end_date=2026-02-28
```

```bash
curl -s http://localhost:8000/api/v1/chargebacks/analysis
```

Returns analysis across 5 dimensions:
- **By country** - Chargeback count, percentage, and total amount per country
- **By product category** - Breakdown across electronics, apparel, home goods
- **By reason code** - Distribution of FRAUD, NOT_RECEIVED, NOT_AS_DESCRIBED, DUPLICATE, OTHER
- **Time-to-chargeback** - Average, median, min, max days and distribution buckets
- **Repeat offenders** - Emails and card BINs with multiple chargebacks

Includes a `summary` field with human-readable insights highlighting the biggest problems.

### Batch Risk Screening (Stretch Goal - Requirement 3)

```
POST /api/v1/transactions/batch-score
```

```bash
curl -s -X POST http://localhost:8000/api/v1/transactions/batch-score \
  -H "Content-Type: application/json" \
  -d '{
    "transactions": [
      {"transaction_id": "b001", "email": "good@gmail.com", "card_bin": "411111", "card_last_four": "1234", "amount": 50.00, "currency": "USD", "billing_country": "BR", "shipping_country": "BR", "ip_country": "BR", "product_category": "apparel", "is_first_purchase": false},
      {"transaction_id": "b002", "email": "risky@guerrillamail.com", "card_bin": "510510", "card_last_four": "5678", "amount": 800.00, "currency": "USD", "billing_country": "BR", "shipping_country": "CO", "ip_country": "MX", "product_category": "electronics", "is_first_purchase": true}
    ]
  }'
```

Returns individual scores for each transaction plus a consolidated summary with action counts. Maximum 500 transactions per batch. Transactions are processed sequentially -- earlier transactions in the batch affect velocity scores of later ones.

### Rule Configuration (Stretch Goal - Requirement 4)

**List rules:**

```
GET /api/v1/rules
```

**Create a rule:**

```
POST /api/v1/rules
```

```bash
curl -s -X POST http://localhost:8000/api/v1/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High-value first-time buyer",
    "description": "Flag transactions over $500 from first-time customers",
    "conditions": [
      {"field": "amount", "operator": "gt", "value": 500},
      {"field": "is_first_purchase", "operator": "eq", "value": true}
    ],
    "action": "MANUAL_REVIEW",
    "risk_score_modifier": 30,
    "priority": 1
  }'
```

Rules support operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`. Cross-field comparison via `value_field`. Virtual fields: `email_domain_disposable` (bool), `velocity_24h` (int).

Three default rules are seeded on startup.

## Architecture

```
app/
  main.py                    # FastAPI app, lifespan, router mounting
  database.py                # SQLite connection, schema, seed loading
  models/
    transaction.py           # Pydantic models for scoring requests/responses
    chargeback.py            # Chargeback analysis response models
    rules.py                 # Rule configuration models
  routers/
    transactions.py          # POST /score, POST /batch-score
    chargebacks.py           # GET /analysis
    rules.py                 # GET/POST /rules
  services/
    risk_scorer.py           # 6-signal risk scoring engine
    chargeback_analyzer.py   # 5-dimension chargeback analysis
    rule_engine.py           # Configurable rule evaluation
    disposable_emails.py     # Disposable email domain list
  seed/
    generate_data.py         # Deterministic test data generator
    transactions.json        # 65 sample transactions
    chargebacks.json         # 260 historical chargebacks
tests/
  conftest.py                # Test client, fixtures, data factories
  test_risk_scoring.py       # 37 tests for risk scoring API
  test_chargeback_analysis.py # 20 tests for chargeback analysis
  test_batch_screening.py    # 12 tests for batch scoring
  test_rules.py              # 16 tests for rule configuration
```

### Key Design Decisions

- **SQLite** - Zero-configuration database, sufficient for this use case. WAL mode enabled for better concurrent read performance.
- **Deterministic scoring** - Same inputs always produce the same risk score. No randomness or ML black boxes. Every risk factor is explicitly explained.
- **Parameterized queries** - All SQL uses `?` placeholders to prevent injection.
- **Modular services** - Risk scorer, chargeback analyzer, and rule engine are independent services called by thin router handlers.
- **Rule engine integration** - Rules are evaluated after the base 6-signal score. Rule modifiers adjust the final score (capped at 0-100), and the most severe action among matching rules overrides the default.
- **Sequential batch processing** - Transactions in a batch are processed in order. Earlier transactions affect velocity checks for later ones. This is intentional fraud-detection behavior.
- **Currency assumed USD** - The `currency` field is accepted but amounts are compared in USD. This is documented as a simplification.

## Test Data

The seed data generator (`python -m app.seed.generate_data`) uses `random.seed(42)` for reproducibility.

**Transactions (65 records):**
- Countries: 40% BR, 35% MX, 25% CO
- Categories: 30% electronics, 40% apparel, 30% home goods
- Planted suspicious patterns: velocity abuse, geo mismatches, high-value new customers, disposable emails, combined red flags
- Planted clean patterns: loyal repeat customers, local transactions, small apparel purchases

**Chargebacks (260 records):**
- Countries: 55% BR, 25% MX, 20% CO (Brazil disproportionately high)
- Categories: 45% electronics, 30% apparel, 25% home goods
- Reason codes: ~49% FRAUD, ~20% NOT_RECEIVED, ~22% NOT_AS_DESCRIBED, ~4% DUPLICATE, ~6% OTHER
- Repeat offenders: 3 email addresses with 4-6 chargebacks each, 2 card BINs with 5-8 each
- Time lag: Normal distribution, mean 47 days, range 18-120 days

To regenerate: `python -m app.seed.generate_data`

## Running Tests

```bash
python -m pytest tests/ -v
```

112 tests covering all endpoints, risk signals, chargeback analysis dimensions, batch processing, rule CRUD, and edge cases. Tests use an in-memory SQLite database for isolation.

## Stretch Goals Status

| Goal | Status |
|------|--------|
| Batch Risk Screening (Req 3) | Complete - batch endpoint with summary counts, max 500 transactions |
| Rule Configuration (Req 4) | Complete - CRUD API, 8 operators, virtual fields, 3 default rules |

## Demo

Run the interactive demo script to see all features in action:

```bash
./demo.sh
```

Or explore the auto-generated API docs at `http://localhost:8000/docs`.
