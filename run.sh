#!/bin/bash
# Quick-start script for Verdant Goods Chargeback Prevention API

set -e

echo "Verdant Goods Chargeback Prevention API"
echo "========================================"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -q

# Generate test data if not present
if [ ! -f "app/seed/transactions.json" ] || [ ! -f "app/seed/chargebacks.json" ]; then
    echo "Generating test data..."
    python -m app.seed.generate_data
fi

# Remove stale database so it gets re-seeded
rm -f verdant_goods.db

echo ""
echo "Starting server on http://localhost:8000"
echo "API docs available at http://localhost:8000/docs"
echo "Press Ctrl+C to stop."
echo ""

uvicorn app.main:app --port 8000
