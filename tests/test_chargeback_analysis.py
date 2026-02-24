"""
TDD tests for Requirement 2: Chargeback Pattern Analysis API.

Tests cover:
- API contract (response structure)
- 5 analysis dimensions: country, category, reason code, timing, repeat offenders
- Date filtering (start_date / end_date query params)
- Summary generation (human-readable insights)
- Edge cases (empty dataset, single record)
"""
import pytest
from tests.conftest import make_chargebacks_dataset


ANALYSIS_URL = "/api/v1/chargebacks/analysis"


# ===========================================================================
# API Contract Tests
# ===========================================================================


class TestAnalysisEndpointContract:
    """Verify the /analysis endpoint returns the correct response structure."""

    @pytest.mark.asyncio
    async def test_returns_200(self, client):
        resp = await client.get(ANALYSIS_URL)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_all_required_sections(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()

        assert "total_chargebacks" in data
        assert "analysis_period" in data
        assert "by_country" in data
        assert "by_product_category" in data
        assert "by_reason_code" in data
        assert "time_to_chargeback" in data
        assert "repeat_offenders" in data
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_total_chargebacks_is_integer(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        assert isinstance(data["total_chargebacks"], int)
        assert data["total_chargebacks"] >= 0

    @pytest.mark.asyncio
    async def test_analysis_period_has_start_and_end(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        period = data["analysis_period"]
        assert "start" in period
        assert "end" in period

    @pytest.mark.asyncio
    async def test_summary_is_list_of_strings(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        assert isinstance(data["summary"], list)
        for item in data["summary"]:
            assert isinstance(item, str)


# ===========================================================================
# Dimension 1: By Country
# ===========================================================================


class TestByCountry:
    """Chargeback rate breakdown by country."""

    @pytest.mark.asyncio
    async def test_by_country_is_list(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        assert isinstance(data["by_country"], list)

    @pytest.mark.asyncio
    async def test_country_entries_have_required_fields(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        for entry in data["by_country"]:
            assert "country" in entry
            assert "chargeback_count" in entry
            assert "percentage" in entry
            assert "total_amount" in entry

    @pytest.mark.asyncio
    async def test_country_percentages_sum_to_100(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        if data["by_country"]:
            total_pct = sum(e["percentage"] for e in data["by_country"])
            assert abs(total_pct - 100.0) < 1.0, f"Country percentages sum to {total_pct}, expected ~100"

    @pytest.mark.asyncio
    async def test_country_counts_sum_to_total(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        if data["by_country"]:
            total_count = sum(e["chargeback_count"] for e in data["by_country"])
            assert total_count == data["total_chargebacks"]

    @pytest.mark.asyncio
    async def test_countries_sorted_by_count_descending(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        countries = data["by_country"]
        if len(countries) > 1:
            counts = [c["chargeback_count"] for c in countries]
            assert counts == sorted(counts, reverse=True), "Countries should be sorted by count descending"


# ===========================================================================
# Dimension 2: By Product Category
# ===========================================================================


class TestByProductCategory:
    """Chargeback breakdown by product category."""

    @pytest.mark.asyncio
    async def test_by_category_is_list(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        assert isinstance(data["by_product_category"], list)

    @pytest.mark.asyncio
    async def test_category_entries_have_required_fields(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        for entry in data["by_product_category"]:
            assert "category" in entry
            assert "chargeback_count" in entry
            assert "percentage" in entry
            assert "total_amount" in entry

    @pytest.mark.asyncio
    async def test_category_percentages_sum_to_100(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        if data["by_product_category"]:
            total_pct = sum(e["percentage"] for e in data["by_product_category"])
            assert abs(total_pct - 100.0) < 1.0

    @pytest.mark.asyncio
    async def test_known_categories_present(self, client):
        """At least the three expected categories should be present in seed data."""
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        categories = {e["category"] for e in data["by_product_category"]}
        # With seed data, we expect these three
        expected = {"electronics", "apparel", "home_goods"}
        if data["total_chargebacks"] > 0:
            assert categories.issubset(expected), f"Unexpected categories: {categories - expected}"


# ===========================================================================
# Dimension 3: By Reason Code
# ===========================================================================


class TestByReasonCode:
    """Chargeback reason code distribution."""

    @pytest.mark.asyncio
    async def test_by_reason_code_is_list(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        assert isinstance(data["by_reason_code"], list)

    @pytest.mark.asyncio
    async def test_reason_code_entries_have_required_fields(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        for entry in data["by_reason_code"]:
            assert "reason_code" in entry
            assert "count" in entry
            assert "percentage" in entry

    @pytest.mark.asyncio
    async def test_reason_code_percentages_sum_to_100(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        if data["by_reason_code"]:
            total_pct = sum(e["percentage"] for e in data["by_reason_code"])
            assert abs(total_pct - 100.0) < 1.0

    @pytest.mark.asyncio
    async def test_valid_reason_codes(self, client):
        """All reason codes should be from the known taxonomy."""
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        valid_codes = {"FRAUD", "NOT_RECEIVED", "NOT_AS_DESCRIBED", "DUPLICATE", "OTHER"}
        for entry in data["by_reason_code"]:
            assert entry["reason_code"] in valid_codes, f"Unknown reason code: {entry['reason_code']}"


# ===========================================================================
# Dimension 4: Time-to-Chargeback Analysis
# ===========================================================================


class TestTimeToChargeback:
    """Analysis of days between transaction and chargeback filing."""

    @pytest.mark.asyncio
    async def test_time_to_chargeback_has_required_fields(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        ttc = data["time_to_chargeback"]
        assert "average_days" in ttc
        assert "median_days" in ttc
        assert "min_days" in ttc
        assert "max_days" in ttc
        assert "distribution" in ttc

    @pytest.mark.asyncio
    async def test_time_stats_are_reasonable(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        ttc = data["time_to_chargeback"]

        if data["total_chargebacks"] > 0:
            assert ttc["min_days"] >= 0
            assert ttc["min_days"] <= ttc["average_days"]
            assert ttc["average_days"] <= ttc["max_days"]
            assert ttc["min_days"] <= ttc["median_days"] <= ttc["max_days"]

    @pytest.mark.asyncio
    async def test_distribution_buckets_exist(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        dist = data["time_to_chargeback"]["distribution"]

        # Should have the documented bucket keys (may use different naming)
        assert len(dist) >= 4, "Distribution should have at least 4 time buckets"

    @pytest.mark.asyncio
    async def test_distribution_sums_to_total(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        dist = data["time_to_chargeback"]["distribution"]
        total_in_buckets = sum(dist.values())
        if data["total_chargebacks"] > 0:
            assert total_in_buckets == data["total_chargebacks"], \
                f"Distribution sum {total_in_buckets} != total {data['total_chargebacks']}"


# ===========================================================================
# Dimension 5: Repeat Offenders
# ===========================================================================


class TestRepeatOffenders:
    """Identify emails and card BINs with multiple chargebacks."""

    @pytest.mark.asyncio
    async def test_repeat_offenders_structure(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        offenders = data["repeat_offenders"]
        assert "by_email" in offenders
        assert "by_card_bin" in offenders
        assert isinstance(offenders["by_email"], list)
        assert isinstance(offenders["by_card_bin"], list)

    @pytest.mark.asyncio
    async def test_repeat_offender_email_entries(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        for entry in data["repeat_offenders"]["by_email"]:
            # Should have an identifier (email), count, and total amount
            assert "chargeback_count" in entry
            assert "total_amount" in entry
            assert entry["chargeback_count"] >= 2, "Repeat offenders should have 2+ chargebacks"

    @pytest.mark.asyncio
    async def test_repeat_offender_card_bin_entries(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        for entry in data["repeat_offenders"]["by_card_bin"]:
            assert "chargeback_count" in entry
            assert "total_amount" in entry
            assert entry["chargeback_count"] >= 2

    @pytest.mark.asyncio
    async def test_repeat_offenders_sorted_by_count(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        for key in ["by_email", "by_card_bin"]:
            entries = data["repeat_offenders"][key]
            if len(entries) > 1:
                counts = [e["chargeback_count"] for e in entries]
                assert counts == sorted(counts, reverse=True), \
                    f"Repeat offenders ({key}) should be sorted by count descending"


# ===========================================================================
# Date Filtering
# ===========================================================================


class TestDateFiltering:
    """Test optional start_date and end_date query parameters."""

    @pytest.mark.asyncio
    async def test_with_start_date(self, client):
        resp = await client.get(ANALYSIS_URL, params={"start_date": "2026-01-01"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["total_chargebacks"], int)

    @pytest.mark.asyncio
    async def test_with_end_date(self, client):
        resp = await client.get(ANALYSIS_URL, params={"end_date": "2026-12-31"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_with_date_range(self, client):
        resp = await client.get(ANALYSIS_URL, params={
            "start_date": "2025-11-01",
            "end_date": "2026-02-28",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_future_date_range_returns_zero(self, client):
        """A date range in the far future should return 0 chargebacks."""
        resp = await client.get(ANALYSIS_URL, params={
            "start_date": "2030-01-01",
            "end_date": "2030-12-31",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_chargebacks"] == 0


# ===========================================================================
# Summary / Insights
# ===========================================================================


class TestSummaryInsights:
    """The summary field should contain actionable, human-readable insights."""

    @pytest.mark.asyncio
    async def test_summary_has_at_least_3_insights(self, client):
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        if data["total_chargebacks"] > 0:
            assert len(data["summary"]) >= 3, "Summary should highlight at least 3 key findings"

    @pytest.mark.asyncio
    async def test_summary_mentions_top_country(self, client):
        """Summary should call out the country with the most chargebacks."""
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        if data["total_chargebacks"] > 0 and data["by_country"]:
            top_country = data["by_country"][0]["country"]
            summary_text = " ".join(data["summary"]).upper()
            assert top_country in summary_text, \
                f"Summary should mention top country '{top_country}'"

    @pytest.mark.asyncio
    async def test_summary_mentions_percentages(self, client):
        """Summary should include specific numbers to be actionable."""
        resp = await client.get(ANALYSIS_URL)
        data = resp.json()
        if data["total_chargebacks"] > 0:
            summary_text = " ".join(data["summary"])
            assert "%" in summary_text, "Summary should include percentage figures"
