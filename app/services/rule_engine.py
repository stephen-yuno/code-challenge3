"""Configurable rule engine for fraud detection.

Evaluates custom rules against transactions. Rules are stored in the database
and applied after the base 6-signal scoring to adjust scores and actions.
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.database import get_connection
from app.models.rules import RuleCondition, RuleResponse
from app.services.disposable_emails import is_disposable_domain


class RuleEngine:
    """Evaluate rules against transaction data."""

    OPERATORS = {
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "in": lambda a, b: a in b,
        "not_in": lambda a, b: a not in b,
    }

    def _resolve_virtual_field(self, field: str, txn_data: Dict[str, Any]) -> Any:
        """Resolve virtual fields computed at evaluation time."""
        if field == "email_domain_disposable":
            email = txn_data.get("email", "")
            return is_disposable_domain(email)
        if field == "velocity_24h":
            from app.services.risk_scorer import get_velocity_count
            email = txn_data.get("email", "")
            ts = txn_data.get("timestamp", datetime.utcnow())
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return get_velocity_count(email, ts)
        return txn_data.get(field)

    def _evaluate_condition(self, cond: RuleCondition, txn_data: Dict[str, Any]) -> bool:
        """Evaluate a single condition against transaction data."""
        field_val = self._resolve_virtual_field(cond.field, txn_data)

        if cond.value_field is not None:
            compare_val = self._resolve_virtual_field(cond.value_field, txn_data)
        else:
            compare_val = cond.value

        op_func = self.OPERATORS.get(cond.operator)
        if op_func is None:
            return False

        try:
            return op_func(field_val, compare_val)
        except (TypeError, ValueError):
            return False

    def evaluate_rule(self, rule: RuleResponse, txn_data: Dict[str, Any]) -> bool:
        """Evaluate all conditions in a rule (AND logic). Returns True if all match."""
        return all(self._evaluate_condition(c, txn_data) for c in rule.conditions)

    def evaluate_all_rules(
        self, txn_data: Dict[str, Any]
    ) -> Tuple[int, Optional[str]]:
        """Evaluate all active rules against a transaction.

        Returns:
            (score_modifier, action_override): Total modifier and the action
            from the highest-priority matching rule, or (0, None) if no rules match.
        """
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM rules WHERE is_active = 1 ORDER BY priority ASC"
        ).fetchall()

        if not rows:
            return 0, None

        total_modifier = 0
        best_action = None
        best_priority = None
        action_severity = {"APPROVE": 0, "MANUAL_REVIEW": 1, "REJECT": 2}

        for row in rows:
            conditions_raw = json.loads(row["conditions"])
            conditions = [RuleCondition(**c) for c in conditions_raw]
            rule = RuleResponse(
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

            if self.evaluate_rule(rule, txn_data):
                total_modifier += rule.risk_score_modifier
                # Use the most severe action among matching rules
                if best_action is None or action_severity.get(rule.action, 0) > action_severity.get(best_action, 0):
                    best_action = rule.action

        return total_modifier, best_action


# Singleton
rule_engine = RuleEngine()
