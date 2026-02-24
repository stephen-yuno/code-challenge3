import json
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter

from app.database import get_connection
from app.models.rules import RuleCondition, RuleRequest, RuleResponse

router = APIRouter(tags=["rules"])


def _row_to_rule(row) -> RuleResponse:
    """Convert a database row to a RuleResponse."""
    conditions_raw = json.loads(row["conditions"])
    conditions = [RuleCondition(**c) for c in conditions_raw]
    return RuleResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        conditions=conditions,
        action=row["action"],
        risk_score_modifier=row["risk_score_modifier"],
        is_active=bool(row["is_active"]),
        priority=row["priority"],
        created_at=row["created_at"],
    )


@router.get("/rules")
async def list_rules():
    """List all configured fraud rules."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM rules ORDER BY priority ASC").fetchall()
    rules = [_row_to_rule(row) for row in rows]
    return {"rules": rules}


@router.post("/rules", status_code=201)
async def create_rule(request: RuleRequest) -> RuleResponse:
    """Create a new fraud rule."""
    conn = get_connection()
    rule_id = f"rule_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    conditions_json = json.dumps([c.model_dump() for c in request.conditions])

    conn.execute(
        """INSERT INTO rules (id, name, description, conditions, action,
           risk_score_modifier, is_active, priority, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rule_id,
            request.name,
            request.description,
            conditions_json,
            request.action,
            request.risk_score_modifier,
            1,
            request.priority,
            now,
        ),
    )
    conn.commit()

    return RuleResponse(
        id=rule_id,
        name=request.name,
        description=request.description,
        conditions=request.conditions,
        action=request.action,
        risk_score_modifier=request.risk_score_modifier,
        is_active=True,
        priority=request.priority,
        created_at=now,
    )
