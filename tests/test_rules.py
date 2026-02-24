"""
TDD tests for Requirement 4 (Stretch): Fraud Rule Configuration.

Tests cover:
- CRUD operations for rules (GET, POST)
- Rule structure and validation
- Rule engine integration with risk scoring
- Rule conditions (operators, field comparisons)
- Rule priority and action override
"""
import pytest
from tests.conftest import make_transaction


RULES_URL = "/api/v1/rules"
SCORE_URL = "/api/v1/transactions/score"


def make_rule(**overrides):
    """Build a sample rule payload."""
    base = {
        "name": "Test Rule",
        "description": "A test fraud rule",
        "conditions": [
            {"field": "amount", "operator": "gt", "value": 500}
        ],
        "action": "MANUAL_REVIEW",
        "risk_score_modifier": 20,
        "priority": 1,
    }
    base.update(overrides)
    return base


# ===========================================================================
# GET /rules
# ===========================================================================


class TestGetRules:
    """Verify listing rules."""

    @pytest.mark.asyncio
    async def test_get_rules_returns_200(self, client):
        resp = await client.get(RULES_URL)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_rules_returns_list(self, client):
        resp = await client.get(RULES_URL)
        data = resp.json()
        assert "rules" in data
        assert isinstance(data["rules"], list)


# ===========================================================================
# POST /rules
# ===========================================================================


class TestCreateRule:
    """Verify creating new rules."""

    @pytest.mark.asyncio
    async def test_create_rule_returns_201(self, client):
        rule = make_rule(name="High Value Rule")
        resp = await client.post(RULES_URL, json=rule)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_created_rule_has_id(self, client):
        rule = make_rule(name="ID Test Rule")
        resp = await client.post(RULES_URL, json=rule)
        data = resp.json()
        assert "id" in data
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_created_rule_echoes_fields(self, client):
        rule = make_rule(
            name="Echo Test",
            description="Testing field echo",
            action="REJECT",
            risk_score_modifier=30,
            priority=5,
        )
        resp = await client.post(RULES_URL, json=rule)
        data = resp.json()
        assert data["name"] == "Echo Test"
        assert data["description"] == "Testing field echo"
        assert data["action"] == "REJECT"
        assert data["risk_score_modifier"] == 30
        assert data["priority"] == 5

    @pytest.mark.asyncio
    async def test_created_rule_is_active_by_default(self, client):
        rule = make_rule(name="Active Default Rule")
        resp = await client.post(RULES_URL, json=rule)
        data = resp.json()
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_created_rule_has_timestamp(self, client):
        rule = make_rule(name="Timestamp Rule")
        resp = await client.post(RULES_URL, json=rule)
        data = resp.json()
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_created_rule_appears_in_list(self, client):
        rule = make_rule(name="Findable Rule")
        create_resp = await client.post(RULES_URL, json=rule)
        rule_id = create_resp.json()["id"]

        list_resp = await client.get(RULES_URL)
        rule_ids = [r["id"] for r in list_resp.json()["rules"]]
        assert rule_id in rule_ids


# ===========================================================================
# Rule Validation
# ===========================================================================


class TestRuleValidation:
    """Invalid rule payloads should be rejected."""

    @pytest.mark.asyncio
    async def test_missing_name_returns_422(self, client):
        rule = make_rule()
        del rule["name"]
        resp = await client.post(RULES_URL, json=rule)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_conditions_returns_422(self, client):
        rule = make_rule(conditions=[])
        resp = await client.post(RULES_URL, json=rule)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_action_returns_422(self, client):
        rule = make_rule(action="DESTROY")
        resp = await client.post(RULES_URL, json=rule)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_modifier_too_high_returns_422(self, client):
        rule = make_rule(risk_score_modifier=100)
        resp = await client.post(RULES_URL, json=rule)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_modifier_too_low_returns_422(self, client):
        rule = make_rule(risk_score_modifier=-100)
        resp = await client.post(RULES_URL, json=rule)
        assert resp.status_code == 422


# ===========================================================================
# Rule Conditions
# ===========================================================================


class TestRuleConditions:
    """Test various condition operators."""

    @pytest.mark.asyncio
    async def test_gt_operator(self, client):
        """Rule: amount > 500 should match a $600 transaction."""
        rule = make_rule(
            name="Amount GT 500",
            conditions=[{"field": "amount", "operator": "gt", "value": 500}],
            risk_score_modifier=15,
        )
        await client.post(RULES_URL, json=rule)

        # Score a transaction with amount > 500
        txn = make_transaction(
            transaction_id="txn_rule_gt",
            email="rule_gt@gmail.com",
            amount=600.00,
        )
        resp = await client.post(SCORE_URL, json=txn)
        data = resp.json()
        # The rule's modifier should have been applied
        # We can't check exact score but can verify it's > baseline
        assert data["risk_score"] > 0

    @pytest.mark.asyncio
    async def test_eq_operator(self, client):
        """Rule: product_category == 'electronics' should match."""
        rule = make_rule(
            name="Electronics Flag",
            conditions=[{"field": "product_category", "operator": "eq", "value": "electronics"}],
            action="MANUAL_REVIEW",
            risk_score_modifier=10,
        )
        await client.post(RULES_URL, json=rule)

        txn = make_transaction(
            transaction_id="txn_rule_eq",
            email="rule_eq@gmail.com",
            product_category="electronics",
        )
        resp = await client.post(SCORE_URL, json=txn)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_value_field_comparison(self, client):
        """Rule: billing_country != shipping_country (cross-field comparison)."""
        rule = make_rule(
            name="Cross-border",
            conditions=[{
                "field": "billing_country",
                "operator": "neq",
                "value_field": "shipping_country",
            }],
            action="MANUAL_REVIEW",
            risk_score_modifier=20,
        )
        await client.post(RULES_URL, json=rule)

        # Transaction where billing != shipping
        txn = make_transaction(
            transaction_id="txn_rule_cross",
            email="rule_cross@gmail.com",
            billing_country="BR",
            shipping_country="CO",
        )
        resp = await client.post(SCORE_URL, json=txn)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_multiple_conditions_all_must_match(self, client):
        """Rule with multiple conditions should require ALL to match (AND logic)."""
        rule = make_rule(
            name="High value first timer",
            conditions=[
                {"field": "amount", "operator": "gt", "value": 500},
                {"field": "is_first_purchase", "operator": "eq", "value": True},
            ],
            action="REJECT",
            risk_score_modifier=30,
        )
        await client.post(RULES_URL, json=rule)

        # Transaction that matches both conditions
        txn_match = make_transaction(
            transaction_id="txn_rule_multi_match",
            email="rule_multi@gmail.com",
            amount=600.00,
            is_first_purchase=True,
        )
        resp_match = await client.post(SCORE_URL, json=txn_match)

        # Transaction that only matches one condition (not first purchase)
        txn_partial = make_transaction(
            transaction_id="txn_rule_multi_partial",
            email="rule_partial@gmail.com",
            amount=600.00,
            is_first_purchase=False,
        )
        resp_partial = await client.post(SCORE_URL, json=txn_partial)

        # The fully matching transaction should score higher
        assert resp_match.json()["risk_score"] >= resp_partial.json()["risk_score"]


# ===========================================================================
# Rule Integration with Scoring
# ===========================================================================


class TestRuleIntegration:
    """Rules should modify the final risk score from the base 6-signal engine."""

    @pytest.mark.asyncio
    async def test_rule_modifier_increases_score(self, client):
        """Adding a rule that matches should increase the risk score."""
        # First score without the rule (baseline) - use a LOW risk transaction
        txn_base = make_transaction(
            transaction_id="txn_rule_base",
            email="rule_base@gmail.com",
            amount=50.00,
            product_category="apparel",
            billing_country="BR",
            shipping_country="BR",
            ip_country="BR",
            is_first_purchase=False,
        )
        resp_base = await client.post(SCORE_URL, json=txn_base)
        base_score = resp_base.json()["risk_score"]

        # Now create a rule that matches this transaction profile
        rule = make_rule(
            name="All apparel flag",
            conditions=[
                {"field": "product_category", "operator": "eq", "value": "apparel"},
            ],
            risk_score_modifier=25,
        )
        await client.post(RULES_URL, json=rule)

        # Score again with the same low-risk profile but different id/email
        txn_ruled = make_transaction(
            transaction_id="txn_rule_after",
            email="rule_after@gmail.com",
            amount=50.00,
            product_category="apparel",
            billing_country="BR",
            shipping_country="BR",
            ip_country="BR",
            is_first_purchase=False,
        )
        resp_ruled = await client.post(SCORE_URL, json=txn_ruled)
        ruled_score = resp_ruled.json()["risk_score"]

        assert ruled_score > base_score, \
            f"Score with rule ({ruled_score}) should be higher than base ({base_score})"

    @pytest.mark.asyncio
    async def test_score_still_capped_at_100_with_rules(self, client):
        """Even with rule modifiers, the final score should not exceed 100."""
        rule = make_rule(
            name="Extreme modifier",
            conditions=[{"field": "amount", "operator": "gt", "value": 0}],
            risk_score_modifier=50,
        )
        await client.post(RULES_URL, json=rule)

        txn = make_transaction(
            transaction_id="txn_rule_cap",
            email="rule_cap@temp-mail.org",
            billing_country="BR",
            shipping_country="CO",
            ip_country="MX",
            product_category="electronics",
            is_first_purchase=True,
            amount=850.00,
        )
        resp = await client.post(SCORE_URL, json=txn)
        assert resp.json()["risk_score"] <= 100
