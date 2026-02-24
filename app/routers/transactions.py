from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.transaction import (
    BatchScoreRequest,
    BatchScoreResponse,
    BatchSummary,
    RiskScoreResponse,
    TransactionRequest,
)
from app.services.risk_scorer import score_transaction

router = APIRouter(tags=["transactions"])


@router.post("/transactions/score", response_model=RiskScoreResponse)
async def score_transaction_endpoint(txn: TransactionRequest) -> RiskScoreResponse:
    """Score a single transaction for fraud risk using 6 independent risk signals."""
    return score_transaction(txn)


@router.post("/transactions/batch-score", response_model=BatchScoreResponse)
async def batch_score_transactions(request: BatchScoreRequest) -> BatchScoreResponse:
    """Score multiple transactions in a single request (max 500)."""
    results = []
    summary_counts = {"APPROVE": 0, "MANUAL_REVIEW": 0, "REJECT": 0}

    for txn in request.transactions:
        result = score_transaction(txn)
        results.append(result)
        summary_counts[result.recommended_action] = summary_counts.get(result.recommended_action, 0) + 1

    return BatchScoreResponse(
        total=len(results),
        scored_at=datetime.now(timezone.utc),
        summary=BatchSummary(
            approve=summary_counts.get("APPROVE", 0),
            manual_review=summary_counts.get("MANUAL_REVIEW", 0),
            reject=summary_counts.get("REJECT", 0),
        ),
        results=results,
    )
