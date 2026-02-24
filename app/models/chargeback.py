from typing import Dict, List

from pydantic import BaseModel, Field


class CountryAnalysis(BaseModel):
    country: str
    chargeback_count: int
    percentage: float
    total_amount: float


class CategoryAnalysis(BaseModel):
    category: str
    chargeback_count: int
    percentage: float
    total_amount: float


class ReasonCodeAnalysis(BaseModel):
    reason_code: str
    count: int
    percentage: float


class TimeDistribution(BaseModel):
    days_0_30: int = Field(alias="0_30_days")
    days_31_60: int = Field(alias="31_60_days")
    days_61_90: int = Field(alias="61_90_days")
    over_90_days: int

    model_config = {"populate_by_name": True}


class TimeToChargeback(BaseModel):
    average_days: float
    median_days: int
    min_days: int
    max_days: int
    distribution: TimeDistribution


class RepeatOffender(BaseModel):
    identifier: str
    chargeback_count: int
    total_amount: float


class RepeatOffenders(BaseModel):
    by_email: List[RepeatOffender]
    by_card_bin: List[RepeatOffender]


class ChargebackAnalysisResponse(BaseModel):
    total_chargebacks: int
    analysis_period: Dict[str, str]
    by_country: List[CountryAnalysis]
    by_product_category: List[CategoryAnalysis]
    by_reason_code: List[ReasonCodeAnalysis]
    time_to_chargeback: TimeToChargeback
    repeat_offenders: RepeatOffenders
    summary: List[str]
