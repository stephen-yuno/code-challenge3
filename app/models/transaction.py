from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


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
    customer_id: Optional[str] = None
    is_first_purchase: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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
