from typing import Optional

from fastapi import APIRouter, Query

from app.models.chargeback import ChargebackAnalysisResponse
from app.services.chargeback_analyzer import analyze_chargebacks

router = APIRouter(tags=["chargebacks"])


@router.get("/chargebacks/analysis", response_model=ChargebackAnalysisResponse)
async def get_chargeback_analysis(
    start_date: Optional[str] = Query(None, description="Filter chargebacks from this date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter chargebacks until this date (YYYY-MM-DD)"),
) -> ChargebackAnalysisResponse:
    """Analyze chargeback patterns across 5 dimensions: country, category,
    reason code, time-to-chargeback, and repeat offenders."""
    return analyze_chargebacks(start_date=start_date, end_date=end_date)
