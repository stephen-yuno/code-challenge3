from __future__ import annotations

from fastapi import APIRouter

from app.models.transaction import RiskScoreResponse, TransactionRequest
from app.services.risk_scorer import score_transaction

router = APIRouter(tags=["transactions"])


@router.post("/transactions/score", response_model=RiskScoreResponse)
async def score_transaction_endpoint(txn: TransactionRequest) -> RiskScoreResponse:
    """Score a single transaction for fraud risk using 6 independent risk signals."""
    return score_transaction(txn)
