"""
TDD tests for Requirement 3 (Stretch): Batch Risk Screening.

Tests cover:
- API contract (batch request/response structure)
- Summary counts (approve, manual_review, reject)
- Batch size limits (max 500)
- Each transaction scored individually
- Order-dependent velocity behavior
"""
import pytest
from tests.conftest import make_transaction, make_low_risk_transaction, make_high_risk_transaction


BATCH_URL = "/api/v1/transactions/batch-score"


# ===========================================================================
# API Contract Tests
# ===========================================================================


class TestBatchEndpointContract:
    """Verify the batch scoring endpoint returns the correct structure."""

    @pytest.mark.asyncio
    async def test_returns_200_with_valid_batch(self, client):
        payload = {
            "transactions": [
                make_transaction(transaction_id="txn_batch_1", email="batch1@gmail.com"),
                make_transaction(transaction_id="txn_batch_2", email="batch2@gmail.com"),
            ]
        }
        resp = await client.post(BATCH_URL, json=payload)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_required_fields(self, client):
        payload = {
            "transactions": [
                make_transaction(transaction_id="txn_batch_3", email="batch3@gmail.com"),
            ]
        }
        resp = await client.post(BATCH_URL, json=payload)
        data = resp.json()

        assert "total" in data
        assert "scored_at" in data
        assert "summary" in data
        assert "results" in data

    @pytest.mark.asyncio
    async def test_summary_has_action_counts(self, client):
        payload = {
            "transactions": [
                make_transaction(transaction_id="txn_batch_4", email="batch4@gmail.com"),
            ]
        }
        resp = await client.post(BATCH_URL, json=payload)
        summary = resp.json()["summary"]

        assert "approve" in summary
        assert "manual_review" in summary
        assert "reject" in summary

    @pytest.mark.asyncio
    async def test_total_matches_input_count(self, client):
        txns = [
            make_transaction(transaction_id=f"txn_batch_count_{i}", email=f"count{i}@gmail.com")
            for i in range(5)
        ]
        resp = await client.post(BATCH_URL, json={"transactions": txns})
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_results_count_matches_input(self, client):
        txns = [
            make_transaction(transaction_id=f"txn_batch_res_{i}", email=f"res{i}@gmail.com")
            for i in range(3)
        ]
        resp = await client.post(BATCH_URL, json={"transactions": txns})
        data = resp.json()
        assert len(data["results"]) == 3


# ===========================================================================
# Summary Counts
# ===========================================================================


class TestBatchSummaryCounts:
    """Summary action counts should match the individual results."""

    @pytest.mark.asyncio
    async def test_summary_counts_match_results(self, client):
        txns = [
            make_low_risk_transaction(transaction_id=f"txn_sum_{i}", email=f"sum{i}@gmail.com")
            for i in range(4)
        ]
        # Add a high-risk one
        txns.append(make_high_risk_transaction(
            transaction_id="txn_sum_high",
            email="sumhigh@temp-mail.org",
        ))

        resp = await client.post(BATCH_URL, json={"transactions": txns})
        data = resp.json()

        # Count from results
        result_actions = [r["recommended_action"] for r in data["results"]]
        expected_approve = result_actions.count("APPROVE")
        expected_review = result_actions.count("MANUAL_REVIEW")
        expected_reject = result_actions.count("REJECT")

        assert data["summary"]["approve"] == expected_approve
        assert data["summary"]["manual_review"] == expected_review
        assert data["summary"]["reject"] == expected_reject

    @pytest.mark.asyncio
    async def test_summary_counts_sum_to_total(self, client):
        txns = [
            make_transaction(transaction_id=f"txn_sumtot_{i}", email=f"sumtot{i}@gmail.com")
            for i in range(3)
        ]
        resp = await client.post(BATCH_URL, json={"transactions": txns})
        data = resp.json()
        summary = data["summary"]
        assert summary["approve"] + summary["manual_review"] + summary["reject"] == data["total"]


# ===========================================================================
# Individual Scoring
# ===========================================================================


class TestBatchIndividualScoring:
    """Each transaction in the batch should be scored individually."""

    @pytest.mark.asyncio
    async def test_each_result_has_score_fields(self, client):
        txns = [
            make_transaction(transaction_id=f"txn_indiv_{i}", email=f"indiv{i}@gmail.com")
            for i in range(2)
        ]
        resp = await client.post(BATCH_URL, json={"transactions": txns})
        for result in resp.json()["results"]:
            assert "transaction_id" in result
            assert "risk_score" in result
            assert "risk_level" in result
            assert "recommended_action" in result
            assert "risk_factors" in result

    @pytest.mark.asyncio
    async def test_low_and_high_risk_scored_differently(self, client):
        txns = [
            make_low_risk_transaction(transaction_id="txn_diff_low", email="difflow@gmail.com"),
            make_high_risk_transaction(transaction_id="txn_diff_high", email="diffhigh@temp-mail.org"),
        ]
        resp = await client.post(BATCH_URL, json={"transactions": txns})
        results = resp.json()["results"]

        low_result = next(r for r in results if r["transaction_id"] == "txn_diff_low")
        high_result = next(r for r in results if r["transaction_id"] == "txn_diff_high")

        assert low_result["risk_score"] < high_result["risk_score"]


# ===========================================================================
# Batch Size Limits
# ===========================================================================


class TestBatchSizeLimits:
    """Batch size must be capped at 500 transactions."""

    @pytest.mark.asyncio
    async def test_empty_batch_returns_422_or_empty(self, client):
        resp = await client.post(BATCH_URL, json={"transactions": []})
        # Either 422 (validation error for empty list) or 200 with total=0
        assert resp.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_batch_over_500_returns_422(self, client):
        txns = [
            make_transaction(transaction_id=f"txn_big_{i}", email=f"big{i}@gmail.com")
            for i in range(501)
        ]
        resp = await client.post(BATCH_URL, json={"transactions": txns})
        assert resp.status_code == 422


# ===========================================================================
# Velocity Order Dependency
# ===========================================================================


class TestBatchVelocityBehavior:
    """
    Transactions in a batch from the same email should show increasing
    velocity scores as earlier ones get recorded.
    """

    @pytest.mark.asyncio
    async def test_same_email_velocity_increases_through_batch(self, client):
        email = "batch_velocity_user@gmail.com"
        txns = [
            make_transaction(
                transaction_id=f"txn_bvel_{i}",
                email=email,
                card_bin="411111",
            )
            for i in range(5)
        ]
        resp = await client.post(BATCH_URL, json={"transactions": txns})
        results = resp.json()["results"]

        # The last transaction should have a higher or equal score than the first
        first_score = results[0]["risk_score"]
        last_score = results[-1]["risk_score"]
        assert last_score >= first_score, \
            "Later transactions from same email should score higher due to velocity"
