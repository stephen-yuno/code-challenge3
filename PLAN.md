# Verdant Goods Chargeback Prevention API - Technical Plan

## Tech Stack

| Component        | Choice          | Rationale                                                  |
|------------------|-----------------|------------------------------------------------------------|
| Language         | Python 3.11+    | Type hints, performance improvements, async support        |
| Framework        | FastAPI         | Async, auto-generated OpenAPI docs, Pydantic integration   |
| Database         | SQLite          | Zero config, file-based, sufficient for this use case      |
| ORM / DB Access  | sqlite3 (stdlib)| Keep it simple; no heavy ORM needed for this scope         |
| Validation       | Pydantic v2     | Already bundled with FastAPI, fast and declarative          |
| Testing          | pytest + httpx  | httpx for async test client with FastAPI                   |
| Data Generation  | Python scripts  | Deterministic seed data with controlled patterns           |

## Project Structure

```
code-challenge3/
├── CHALLENGE.md
├── PLAN.md
├── README.md
├── requirements.txt
├── run.sh                        # Quick-start script
├── demo.sh                       # Demo script with curl examples
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app, lifespan, router mounting
│   ├── database.py               # SQLite connection, schema init, seed loading
│   ├── models/
│   │   ├── __init__.py
│   │   ├── transaction.py        # Transaction request/response models
│   │   ├── chargeback.py         # Chargeback data models
│   │   └── rules.py              # Rule configuration models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── transactions.py       # POST /score, POST /batch-score
│   │   ├── chargebacks.py        # GET /analysis
│   │   └── rules.py              # GET/POST /rules
│   ├── services/
│   │   ├── __init__.py
│   │   ├── risk_scorer.py        # Core risk scoring engine
│   │   ├── chargeback_analyzer.py# Chargeback pattern analysis
│   │   ├── rule_engine.py        # Configurable rule evaluation
│   │   └── disposable_emails.py  # Disposable email domain list
│   └── seed/
│       ├── generate_data.py      # Test data generation script
│       ├── transactions.json     # 50+ sample transactions
│       └── chargebacks.json      # 200+ historical chargebacks
└── tests/
    ├── __init__.py
    ├── conftest.py               # Shared fixtures (test client, test DB)
    ├── test_risk_scoring.py
    ├── test_chargeback_analysis.py
    ├── test_batch_screening.py
    └── test_rules.py
```

## Database Schema

We use SQLite with three tables. The DB is initialized on app startup and seeded from JSON files.

### Table: `transactions`

Stores all known transactions (used for velocity checks and historical lookups).

```sql
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    card_bin TEXT NOT NULL,           -- first 6 digits
    card_last_four TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    billing_country TEXT NOT NULL,    -- ISO 3166 alpha-2
    shipping_country TEXT NOT NULL,
    ip_country TEXT NOT NULL,
    product_category TEXT NOT NULL,   -- electronics | apparel | home_goods
    customer_id TEXT,
    is_first_purchase INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL          -- ISO 8601
);
```

### Table: `chargebacks`

Stores historical chargeback records for pattern analysis.

```sql
CREATE TABLE IF NOT EXISTS chargebacks (
    id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    chargeback_date TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    country TEXT NOT NULL,
    product_category TEXT NOT NULL,
    reason_code TEXT NOT NULL,        -- FRAUD | NOT_RECEIVED | NOT_AS_DESCRIBED | DUPLICATE | OTHER
    email TEXT NOT NULL,
    card_bin TEXT NOT NULL
);
```

### Table: `rules`

Stores custom fraud rules (stretch goal).

```sql
CREATE TABLE IF NOT EXISTS rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    conditions TEXT NOT NULL,         -- JSON array of condition objects
    action TEXT NOT NULL,             -- APPROVE | MANUAL_REVIEW | REJECT
    risk_score_modifier INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
```

## API Endpoints

### Requirement 1: Risk Scoring API

#### `POST /api/v1/transactions/score`

**Request Body:**

```json
{
  "transaction_id": "txn_abc123",
  "email": "customer@example.com",
  "card_bin": "411111",
  "card_last_four": "1234",
  "amount": 350.00,
  "currency": "USD",
  "billing_country": "BR",
  "shipping_country": "BR",
  "ip_country": "BR",
  "product_category": "electronics",
  "customer_id": "cust_001",
  "is_first_purchase": false,
  "timestamp": "2026-02-24T14:30:00Z"
}
```

**Response (200 OK):**

```json
{
  "transaction_id": "txn_abc123",
  "risk_score": 62,
  "risk_level": "HIGH",
  "recommended_action": "MANUAL_REVIEW",
  "risk_factors": [
    {
      "signal": "high_risk_category",
      "score": 15,
      "description": "Product category 'electronics' has elevated chargeback rates"
    },
    {
      "signal": "amount_anomaly",
      "score": 12,
      "description": "Transaction amount ($350.00) exceeds average order value by 2.1x"
    }
  ],
  "scored_at": "2026-02-24T14:30:01Z"
}
```

**Error Responses:**
- `422 Unprocessable Entity` - Invalid input (Pydantic validation failure)

---

### Risk Scoring Algorithm

The scoring engine evaluates 6 independent risk signals. Each signal produces a sub-score between 0 and a defined maximum. The final score is the sum, capped at 100.

| # | Signal                  | Max Points | Logic                                                                                                 |
|---|-------------------------|------------|-------------------------------------------------------------------------------------------------------|
| 1 | Velocity checks         | 25         | Count transactions from same email/card_bin/IP in last 24h. 0-1=0pts, 2-3=5pts, 4-6=15pts, 7+=25pts |
| 2 | Geolocation mismatch    | 20         | Compare billing, shipping, and IP countries. Any pair mismatch=10pts each, all three differ=20pts     |
| 3 | High-risk category      | 15         | electronics=15pts, home_goods=5pts, apparel=0pts                                                      |
| 4 | Amount anomaly          | 20         | Compare to avg order value. 1-2x=0pts, 2-3x=8pts, 3-5x=14pts, >5x=20pts                             |
| 5 | New customer risk       | 10         | is_first_purchase=true AND amount>$200=10pts; is_first_purchase=true AND amount<=$200=5pts; else=0    |
| 6 | Email/domain patterns   | 10         | Disposable domain=10pts; random-looking local part (entropy check)=5pts                               |

**Total possible: 100 points.**

**Risk level mapping:**
- 0-25: `LOW` -> `APPROVE`
- 26-50: `MEDIUM` -> `APPROVE` (with note)
- 51-75: `HIGH` -> `MANUAL_REVIEW`
- 76-100: `CRITICAL` -> `REJECT`

The algorithm is fully deterministic: same inputs always produce the same score.

**Velocity check detail:** We query the `transactions` table for records matching the email, card_bin, or IP within the last 24 hours from the given timestamp. The highest count among the three dimensions is used. Each scored transaction is also inserted into the transactions table so future velocity checks reflect it.

**Geolocation mismatch detail:** We compare three country fields pairwise: (billing, shipping), (billing, IP), (shipping, IP). Each mismatched pair adds 10 points, capped at 20.

**Amount anomaly detail:** The average order value is computed from the transactions table. If no history exists, a default AOV of $120 is used (derived from Verdant Goods' product mix).

**Email pattern detail:** We maintain a hardcoded list of ~30 known disposable email domains (temp-mail.org, guerrillamail.com, mailinator.com, etc.). For entropy checking, we compute the ratio of unique characters to total length in the local part; ratios above 0.85 with length > 12 are flagged.

---

### Requirement 2: Chargeback Pattern Analysis

#### `GET /api/v1/chargebacks/analysis`

No request body. Optional query parameters:

| Parameter     | Type   | Default | Description                        |
|---------------|--------|---------|------------------------------------|
| `start_date`  | string | none    | Filter chargebacks from this date  |
| `end_date`    | string | none    | Filter chargebacks until this date |

**Response (200 OK):**

```json
{
  "total_chargebacks": 234,
  "analysis_period": {
    "start": "2025-11-01",
    "end": "2026-02-24"
  },
  "by_country": [
    {
      "country": "BR",
      "chargeback_count": 142,
      "percentage": 60.7,
      "total_amount": 48230.50
    },
    {
      "country": "MX",
      "chargeback_count": 58,
      "percentage": 24.8,
      "total_amount": 19450.00
    },
    {
      "country": "CO",
      "chargeback_count": 34,
      "percentage": 14.5,
      "total_amount": 11200.00
    }
  ],
  "by_product_category": [
    {
      "category": "electronics",
      "chargeback_count": 120,
      "percentage": 51.3,
      "total_amount": 52100.00
    },
    {
      "category": "apparel",
      "chargeback_count": 65,
      "percentage": 27.8,
      "total_amount": 13500.00
    },
    {
      "category": "home_goods",
      "chargeback_count": 49,
      "percentage": 20.9,
      "total_amount": 12830.50
    }
  ],
  "by_reason_code": [
    {
      "reason_code": "FRAUD",
      "count": 98,
      "percentage": 41.9
    },
    {
      "reason_code": "NOT_RECEIVED",
      "count": 62,
      "percentage": 26.5
    },
    {
      "reason_code": "NOT_AS_DESCRIBED",
      "count": 44,
      "percentage": 18.8
    },
    {
      "reason_code": "DUPLICATE",
      "count": 18,
      "percentage": 7.7
    },
    {
      "reason_code": "OTHER",
      "count": 12,
      "percentage": 5.1
    }
  ],
  "time_to_chargeback": {
    "average_days": 47.3,
    "median_days": 42,
    "min_days": 18,
    "max_days": 118,
    "distribution": {
      "0_30_days": 52,
      "31_60_days": 108,
      "61_90_days": 58,
      "over_90_days": 16
    }
  },
  "repeat_offenders": {
    "by_email": [
      {
        "email": "suspicious_buyer@temp-mail.org",
        "chargeback_count": 5,
        "total_amount": 2340.00
      }
    ],
    "by_card_bin": [
      {
        "card_bin": "510510",
        "chargeback_count": 8,
        "total_amount": 3890.00
      }
    ]
  },
  "summary": [
    "Brazil accounts for 60.7% of all chargebacks, significantly above its transaction share",
    "Electronics have the highest chargeback rate at 51.3% of all disputes",
    "FRAUD is the leading reason code at 41.9%, suggesting stolen card usage",
    "Average time to chargeback is 47.3 days, with 74.4% filed within 60 days",
    "3 email addresses and 2 card BINs are repeat offenders with 3+ chargebacks each"
  ]
}
```

**Implementation approach:** All aggregations are done via SQL queries against the `chargebacks` table. Each analysis dimension is a separate query for clarity and maintainability. The `summary` field is generated programmatically based on the computed data (not LLM-generated) to highlight the most significant findings.

---

### Requirement 3 (Stretch): Batch Risk Screening

#### `POST /api/v1/transactions/batch-score`

**Request Body:**

```json
{
  "transactions": [
    { "transaction_id": "txn_001", "email": "...", ... },
    { "transaction_id": "txn_002", "email": "...", ... }
  ]
}
```

**Response (200 OK):**

```json
{
  "total": 50,
  "scored_at": "2026-02-24T08:00:00Z",
  "summary": {
    "approve": 35,
    "manual_review": 10,
    "reject": 5
  },
  "results": [
    {
      "transaction_id": "txn_001",
      "risk_score": 12,
      "risk_level": "LOW",
      "recommended_action": "APPROVE",
      "risk_factors": []
    },
    {
      "transaction_id": "txn_002",
      "risk_score": 78,
      "risk_level": "CRITICAL",
      "recommended_action": "REJECT",
      "risk_factors": [...]
    }
  ]
}
```

**Implementation:** Iterate over the transaction list and score each one with the same `risk_scorer.py` engine. Returns a consolidated report with a summary of action counts. We cap the batch at 500 transactions per request to stay within reasonable processing time.

---

### Requirement 4 (Stretch): Rule Configuration

#### `GET /api/v1/rules`

Returns all configured rules.

```json
{
  "rules": [
    {
      "id": "rule_001",
      "name": "High-value first-time buyer",
      "description": "Flag any transaction over $500 from a first-time customer as HIGH risk",
      "conditions": [
        { "field": "amount", "operator": "gt", "value": 500 },
        { "field": "is_first_purchase", "operator": "eq", "value": true }
      ],
      "action": "MANUAL_REVIEW",
      "risk_score_modifier": 30,
      "is_active": true,
      "priority": 1
    }
  ]
}
```

#### `POST /api/v1/rules`

Create a new rule.

**Request Body:**

```json
{
  "name": "Cross-border disposable email",
  "description": "Auto-reject cross-border transactions with disposable email",
  "conditions": [
    { "field": "billing_country", "operator": "neq", "value_field": "shipping_country" },
    { "field": "email_domain_disposable", "operator": "eq", "value": true }
  ],
  "action": "REJECT",
  "risk_score_modifier": 50,
  "priority": 2
}
```

**Response (201 Created):** Returns the created rule with generated `id`.

**Rule Engine Design:**

The rule engine supports these operators:
- `eq`, `neq` - equality / inequality
- `gt`, `gte`, `lt`, `lte` - numeric comparisons
- `in`, `not_in` - membership in a list
- `value_field` - compare against another field on the transaction (instead of a static `value`)

Virtual fields derived at evaluation time:
- `email_domain_disposable` (bool) - is the email domain on the disposable list
- `velocity_24h` (int) - transaction count in last 24h for this email

Rules are evaluated in priority order. Each matching rule's `risk_score_modifier` is added to the base score. The rule's `action` can override the default action if the rule is the highest-priority match that fires.

Rules integrate with the scoring engine: after computing the base 6-signal score, active rules are evaluated. Their modifiers adjust the final score (still capped at 100), and the most severe action among all matching rules is used.

---

## Pydantic Models

### Transaction Input (`models/transaction.py`)

```python
class TransactionRequest(BaseModel):
    transaction_id: str
    email: str
    card_bin: str = Field(min_length=6, max_length=6)
    card_last_four: str = Field(min_length=4, max_length=4)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=3)
    billing_country: str = Field(min_length=2, max_length=2)
    shipping_country: str = Field(min_length=2, max_length=2)
    ip_country: str = Field(min_length=2, max_length=2)
    product_category: Literal["electronics", "apparel", "home_goods"]
    customer_id: str | None = None
    is_first_purchase: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### Risk Score Response

```python
class RiskFactor(BaseModel):
    signal: str
    score: int
    description: str

class RiskScoreResponse(BaseModel):
    transaction_id: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    recommended_action: Literal["APPROVE", "MANUAL_REVIEW", "REJECT"]
    risk_factors: list[RiskFactor]
    scored_at: datetime
```

### Batch Request/Response

```python
class BatchScoreRequest(BaseModel):
    transactions: list[TransactionRequest] = Field(max_length=500)

class BatchSummary(BaseModel):
    approve: int
    manual_review: int
    reject: int

class BatchScoreResponse(BaseModel):
    total: int
    scored_at: datetime
    summary: BatchSummary
    results: list[RiskScoreResponse]
```

### Chargeback Analysis Response

```python
class CountryAnalysis(BaseModel):
    country: str
    chargeback_count: int
    percentage: float
    total_amount: float

class CategoryAnalysis(BaseModel):
    category: str
    chargeback_count: int
    percentage: float
    total_amount: float

class ReasonCodeAnalysis(BaseModel):
    reason_code: str
    count: int
    percentage: float

class TimeDistribution(BaseModel):
    days_0_30: int = Field(alias="0_30_days")
    days_31_60: int = Field(alias="31_60_days")
    days_61_90: int = Field(alias="61_90_days")
    over_90_days: int

class TimeToChargeback(BaseModel):
    average_days: float
    median_days: int
    min_days: int
    max_days: int
    distribution: TimeDistribution

class RepeatOffender(BaseModel):
    identifier: str   # email or card_bin
    chargeback_count: int
    total_amount: float

class RepeatOffenders(BaseModel):
    by_email: list[RepeatOffender]
    by_card_bin: list[RepeatOffender]

class ChargebackAnalysisResponse(BaseModel):
    total_chargebacks: int
    analysis_period: dict
    by_country: list[CountryAnalysis]
    by_product_category: list[CategoryAnalysis]
    by_reason_code: list[ReasonCodeAnalysis]
    time_to_chargeback: TimeToChargeback
    repeat_offenders: RepeatOffenders
    summary: list[str]
```

### Rule Models

```python
class RuleCondition(BaseModel):
    field: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"]
    value: Any = None
    value_field: str | None = None  # compare to another transaction field

class RuleRequest(BaseModel):
    name: str
    description: str | None = None
    conditions: list[RuleCondition] = Field(min_length=1)
    action: Literal["APPROVE", "MANUAL_REVIEW", "REJECT"]
    risk_score_modifier: int = Field(default=0, ge=-50, le=50)
    priority: int = Field(default=0, ge=0)

class RuleResponse(RuleRequest):
    id: str
    is_active: bool
    created_at: datetime
```

---

## Test Data Strategy

### Generation Script (`app/seed/generate_data.py`)

The script uses Python's `random` module with a fixed seed (`random.seed(42)`) for reproducibility.

### Transactions (50+ records)

Distribution:
- **Countries:** 40% BR, 35% MX, 25% CO
- **Categories:** 30% electronics, 40% apparel, 30% home_goods
- **Amounts:** Normal distribution centered at $120, range $15-$850
- **Customer types:** 60% repeat, 40% first-time

Planted suspicious patterns (10-12 transactions):
1. **Velocity abuse:** 3 records with the same email `speed_buyer@temp-mail.org` within 1 hour
2. **Geo mismatch:** 3 records where billing=BR, shipping=CO, IP=MX
3. **High-value new customer:** 2 records with first-time buyers spending $600+
4. **Disposable emails:** 3 records using domains from the disposable list
5. **Combined red flags:** 1 record combining velocity + geo mismatch + disposable email (should score near 100)

Planted clean patterns (10-12 transactions):
1. **Loyal repeat customer:** Same email, same country, moderate amounts
2. **Local match:** All three geo fields identical, reasonable amount
3. **Small apparel purchase:** Low amount, repeat buyer, same country

### Chargebacks (200+ records)

Distribution designed to show clear patterns:
- **Countries:** 55% BR, 25% MX, 20% CO (Brazil disproportionately high)
- **Categories:** 45% electronics, 30% apparel, 25% home_goods
- **Reason codes:** 40% FRAUD, 25% NOT_RECEIVED, 20% NOT_AS_DESCRIBED, 10% DUPLICATE, 5% OTHER
- **Time lag:** Normal distribution mean=47 days, std=20 days, clamped to 18-120 days

Planted patterns:
1. **Repeat offenders:** 3 email addresses with 4-6 chargebacks each
2. **Repeat card BINs:** 2 BINs with 5-8 chargebacks each
3. **Brazil FRAUD concentration:** 70% of FRAUD reason codes come from BR
4. **Electronics NOT_AS_DESCRIBED:** Electronics have 3x the NOT_AS_DESCRIBED rate vs other categories
5. **Seasonal spike:** Chargebacks from December transactions are 2x the normal rate

---

## Implementation Order

### Phase 1: Foundation (Task #3)
1. Create project structure (all directories and `__init__.py` files)
2. Set up `requirements.txt` (fastapi, uvicorn, pydantic, httpx, pytest, pytest-asyncio)
3. Implement `database.py` (connection management, schema creation, seed loading)
4. Define all Pydantic models in `models/`
5. Create `main.py` with FastAPI app and health check endpoint
6. Generate seed data (`generate_data.py` -> JSON files)

### Phase 2: Risk Scoring (Task #4)
1. Implement `disposable_emails.py` with domain list
2. Build `risk_scorer.py` with 6 signal evaluators
3. Create `routers/transactions.py` with `POST /score` endpoint
4. Write tests for each risk signal independently
5. Write integration tests for the full scoring endpoint

### Phase 3: Chargeback Analysis (Task #5)
1. Build `chargeback_analyzer.py` with 5 analysis dimensions
2. Create `routers/chargebacks.py` with `GET /analysis` endpoint
3. Write tests validating analysis output against known seed data patterns
4. Generate the `summary` field with programmatic insight text

### Phase 4: Test Data (Task #6)
1. Finalize `generate_data.py` with all planted patterns
2. Generate `transactions.json` (50+ records)
3. Generate `chargebacks.json` (200+ records)
4. Validate data loads correctly and produces expected analysis results

### Phase 5: Stretch Goals (Task #7)
1. Implement batch scoring endpoint (reuses `risk_scorer.py`)
2. Implement rule engine (`rule_engine.py`)
3. Create rule CRUD endpoints
4. Integrate rule engine with risk scorer
5. Seed 2-3 default rules

### Phase 6: Polish (Task #8)
1. Write comprehensive tests for all endpoints
2. Write README.md with setup instructions, API docs, architecture notes
3. Create `demo.sh` with curl-based demo walkthrough
4. Create `run.sh` for quick start
5. Final review pass
