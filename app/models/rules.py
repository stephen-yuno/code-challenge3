from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class RuleCondition(BaseModel):
    field: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"]
    value: Any = None
    value_field: Optional[str] = None


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
