#!/bin/bash
# Demo script for Verdant Goods Chargeback Prevention API
# Shows all endpoints in action

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}========================================${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}========================================${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${BOLD}${GREEN}--- $1 ---${NC}"
    echo ""
}

pause() {
    echo ""
    echo -e "${YELLOW}Press Enter to continue...${NC}"
    read -r
}

# Check if server is running
if ! curl -s "$BASE_URL/health" > /dev/null 2>&1; then
    echo "Server is not running at $BASE_URL"
    echo "Start it with: uvicorn app.main:app --port 8000"
    exit 1
fi

print_header "Verdant Goods Chargeback Prevention API Demo"

echo "Server is running at $BASE_URL"
echo ""
echo "This demo walks through all API endpoints:"
echo "  1. Health check"
echo "  2. Risk scoring (clean transaction)"
echo "  3. Risk scoring (suspicious transaction)"
echo "  4. Chargeback pattern analysis"
echo "  5. Batch risk screening"
echo "  6. Rule configuration"

pause

# ============================================================
# 1. Health Check
# ============================================================

print_header "1. Health Check"

echo "GET /health"
echo ""
curl -s "$BASE_URL/health" | python3 -m json.tool
pause

# ============================================================
# 2. Risk Scoring - Clean Transaction
# ============================================================

print_header "2. Risk Scoring - Clean Transaction"

echo "POST /api/v1/transactions/score"
echo ""
echo "Scoring a repeat customer from Brazil buying apparel for \$45:"
echo ""

curl -s -X POST "$BASE_URL/api/v1/transactions/score" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "demo_clean_001",
    "email": "maria.silva@gmail.com",
    "card_bin": "411111",
    "card_last_four": "4242",
    "amount": 45.00,
    "currency": "USD",
    "billing_country": "BR",
    "shipping_country": "BR",
    "ip_country": "BR",
    "product_category": "apparel",
    "is_first_purchase": false
  }' | python3 -m json.tool

echo ""
echo "Result: LOW risk, APPROVE - no red flags detected."
pause

# ============================================================
# 3. Risk Scoring - Suspicious Transaction
# ============================================================

print_header "3. Risk Scoring - Suspicious Transaction"

echo "POST /api/v1/transactions/score"
echo ""
echo "Scoring a first-time buyer with:"
echo "  - Disposable email (temp-mail.org)"
echo "  - Country mismatch (billing=BR, shipping=CO, IP=MX)"
echo "  - Electronics purchase for \$750"
echo ""

curl -s -X POST "$BASE_URL/api/v1/transactions/score" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "demo_suspicious_001",
    "email": "xk7q9m2p@temp-mail.org",
    "card_bin": "510510",
    "card_last_four": "0001",
    "amount": 750.00,
    "currency": "USD",
    "billing_country": "BR",
    "shipping_country": "CO",
    "ip_country": "MX",
    "product_category": "electronics",
    "is_first_purchase": true
  }' | python3 -m json.tool

echo ""
echo "Result: CRITICAL risk, REJECT - multiple red flags triggered."
pause

# ============================================================
# 4. Chargeback Pattern Analysis
# ============================================================

print_header "4. Chargeback Pattern Analysis"

echo "GET /api/v1/chargebacks/analysis"
echo ""
echo "Analyzing 260+ historical chargebacks across 5 dimensions..."
echo ""

curl -s "$BASE_URL/api/v1/chargebacks/analysis" | python3 -m json.tool

echo ""
echo "Key findings from the analysis:"
echo "  - Brazil accounts for ~56% of chargebacks"
echo "  - Electronics have the highest chargeback rate (~45%)"
echo "  - FRAUD is the leading reason code (~49%)"
echo "  - Average time to chargeback is ~47 days"
echo "  - Multiple repeat offender emails and card BINs identified"
pause

# ============================================================
# 5. Batch Risk Screening
# ============================================================

print_header "5. Batch Risk Screening (Stretch Goal)"

echo "POST /api/v1/transactions/batch-score"
echo ""
echo "Screening 3 transactions in a single batch..."
echo ""

curl -s -X POST "$BASE_URL/api/v1/transactions/batch-score" \
  -H "Content-Type: application/json" \
  -d '{
    "transactions": [
      {
        "transaction_id": "batch_001",
        "email": "loyal.customer@gmail.com",
        "card_bin": "411111",
        "card_last_four": "4242",
        "amount": 65.00,
        "currency": "USD",
        "billing_country": "MX",
        "shipping_country": "MX",
        "ip_country": "MX",
        "product_category": "home_goods",
        "is_first_purchase": false
      },
      {
        "transaction_id": "batch_002",
        "email": "new.shopper@outlook.com",
        "card_bin": "510510",
        "card_last_four": "5678",
        "amount": 250.00,
        "currency": "USD",
        "billing_country": "CO",
        "shipping_country": "CO",
        "ip_country": "CO",
        "product_category": "electronics",
        "is_first_purchase": true
      },
      {
        "transaction_id": "batch_003",
        "email": "sketchy@guerrillamail.com",
        "card_bin": "340000",
        "card_last_four": "9999",
        "amount": 800.00,
        "currency": "USD",
        "billing_country": "BR",
        "shipping_country": "MX",
        "ip_country": "CO",
        "product_category": "electronics",
        "is_first_purchase": true
      }
    ]
  }' | python3 -m json.tool

echo ""
echo "The batch summary shows action counts for quick triage."
pause

# ============================================================
# 6. Rule Configuration
# ============================================================

print_header "6. Rule Configuration (Stretch Goal)"

print_section "List existing rules"
echo "GET /api/v1/rules"
echo ""

curl -s "$BASE_URL/api/v1/rules" | python3 -m json.tool

pause

print_section "Create a new rule"
echo "POST /api/v1/rules"
echo ""
echo "Creating rule: 'Reject large electronics from disposable emails'"
echo ""

curl -s -X POST "$BASE_URL/api/v1/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Large electronics + disposable email",
    "description": "Auto-reject electronics over $400 from disposable email domains",
    "conditions": [
      {"field": "product_category", "operator": "eq", "value": "electronics"},
      {"field": "amount", "operator": "gt", "value": 400},
      {"field": "email_domain_disposable", "operator": "eq", "value": true}
    ],
    "action": "REJECT",
    "risk_score_modifier": 40,
    "priority": 1
  }' | python3 -m json.tool

echo ""
echo "New rule created and will be applied to future transactions."

# ============================================================
# Done
# ============================================================

print_header "Demo Complete"

echo "All endpoints working correctly."
echo ""
echo "Explore the interactive API docs at: $BASE_URL/docs"
echo ""
echo "Run the test suite: python -m pytest tests/ -v"
echo ""
