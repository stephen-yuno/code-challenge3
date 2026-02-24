from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.database import get_connection
from app.models.chargeback import (
    CategoryAnalysis,
    ChargebackAnalysisResponse,
    CountryAnalysis,
    ReasonCodeAnalysis,
    RepeatOffender,
    RepeatOffenders,
    TimeDistribution,
    TimeToChargeback,
)


def _build_date_filter(start_date: Optional[str], end_date: Optional[str]) -> Tuple[str, list]:
    """Build SQL WHERE clause for date filtering."""
    clauses = []
    params = []
    if start_date:
        clauses.append("chargeback_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("chargeback_date <= ?")
        params.append(end_date)
    where = " AND ".join(clauses) if clauses else "1=1"
    return where, params


def _analyze_by_country(where: str, params: list, total: int) -> List[CountryAnalysis]:
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT country, COUNT(*) as cnt, SUM(amount) as total_amount
            FROM chargebacks WHERE {where}
            GROUP BY country ORDER BY cnt DESC""",
        params,
    ).fetchall()
    return [
        CountryAnalysis(
            country=r["country"],
            chargeback_count=r["cnt"],
            percentage=round(r["cnt"] / total * 100, 1) if total > 0 else 0,
            total_amount=round(r["total_amount"], 2),
        )
        for r in rows
    ]


def _analyze_by_category(where: str, params: list, total: int) -> List[CategoryAnalysis]:
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT product_category, COUNT(*) as cnt, SUM(amount) as total_amount
            FROM chargebacks WHERE {where}
            GROUP BY product_category ORDER BY cnt DESC""",
        params,
    ).fetchall()
    return [
        CategoryAnalysis(
            category=r["product_category"],
            chargeback_count=r["cnt"],
            percentage=round(r["cnt"] / total * 100, 1) if total > 0 else 0,
            total_amount=round(r["total_amount"], 2),
        )
        for r in rows
    ]


def _analyze_by_reason_code(where: str, params: list, total: int) -> List[ReasonCodeAnalysis]:
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT reason_code, COUNT(*) as cnt
            FROM chargebacks WHERE {where}
            GROUP BY reason_code ORDER BY cnt DESC""",
        params,
    ).fetchall()
    return [
        ReasonCodeAnalysis(
            reason_code=r["reason_code"],
            count=r["cnt"],
            percentage=round(r["cnt"] / total * 100, 1) if total > 0 else 0,
        )
        for r in rows
    ]


def _analyze_time_to_chargeback(where: str, params: list) -> TimeToChargeback:
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT julianday(chargeback_date) - julianday(transaction_date) as days_diff
            FROM chargebacks WHERE {where}
            ORDER BY days_diff""",
        params,
    ).fetchall()

    if not rows:
        return TimeToChargeback(
            average_days=0,
            median_days=0,
            min_days=0,
            max_days=0,
            distribution=TimeDistribution(**{
                "0_30_days": 0, "31_60_days": 0, "61_90_days": 0, "over_90_days": 0
            }),
        )

    days_list = [int(round(r["days_diff"])) for r in rows]
    avg_days = round(sum(days_list) / len(days_list), 1)
    sorted_days = sorted(days_list)
    n = len(sorted_days)
    if n % 2 == 0:
        median = (sorted_days[n // 2 - 1] + sorted_days[n // 2]) // 2
    else:
        median = sorted_days[n // 2]

    dist = {"0_30_days": 0, "31_60_days": 0, "61_90_days": 0, "over_90_days": 0}
    for d in days_list:
        if d <= 30:
            dist["0_30_days"] += 1
        elif d <= 60:
            dist["31_60_days"] += 1
        elif d <= 90:
            dist["61_90_days"] += 1
        else:
            dist["over_90_days"] += 1

    return TimeToChargeback(
        average_days=avg_days,
        median_days=median,
        min_days=min(days_list),
        max_days=max(days_list),
        distribution=TimeDistribution(**dist),
    )


def _analyze_repeat_offenders(where: str, params: list) -> RepeatOffenders:
    conn = get_connection()

    email_rows = conn.execute(
        f"""SELECT email, COUNT(*) as cnt, SUM(amount) as total_amount
            FROM chargebacks WHERE {where}
            GROUP BY email HAVING cnt >= 2
            ORDER BY cnt DESC""",
        params,
    ).fetchall()

    card_rows = conn.execute(
        f"""SELECT card_bin, COUNT(*) as cnt, SUM(amount) as total_amount
            FROM chargebacks WHERE {where}
            GROUP BY card_bin HAVING cnt >= 2
            ORDER BY cnt DESC""",
        params,
    ).fetchall()

    return RepeatOffenders(
        by_email=[
            RepeatOffender(
                identifier=r["email"],
                chargeback_count=r["cnt"],
                total_amount=round(r["total_amount"], 2),
            )
            for r in email_rows
        ],
        by_card_bin=[
            RepeatOffender(
                identifier=r["card_bin"],
                chargeback_count=r["cnt"],
                total_amount=round(r["total_amount"], 2),
            )
            for r in card_rows
        ],
    )


def _generate_summary(
    total: int,
    by_country: List[CountryAnalysis],
    by_category: List[CategoryAnalysis],
    by_reason: List[ReasonCodeAnalysis],
    time_info: TimeToChargeback,
    offenders: RepeatOffenders,
) -> List[str]:
    summary = []

    if by_country:
        top = by_country[0]
        summary.append(
            f"{top.country} accounts for {top.percentage}% of all chargebacks, "
            f"significantly above its transaction share"
        )

    if by_category:
        top = by_category[0]
        summary.append(
            f"{top.category.capitalize()} have the highest chargeback rate at "
            f"{top.percentage}% of all disputes"
        )

    if by_reason:
        top = by_reason[0]
        reason_desc = {
            "FRAUD": "suggesting stolen card usage",
            "NOT_RECEIVED": "indicating delivery issues",
            "NOT_AS_DESCRIBED": "suggesting product quality concerns",
            "DUPLICATE": "indicating billing system issues",
            "OTHER": "requiring further investigation",
        }
        desc = reason_desc.get(top.reason_code, "")
        summary.append(
            f"{top.reason_code} is the leading reason code at {top.percentage}%"
            + (f", {desc}" if desc else "")
        )

    if total > 0:
        within_60 = time_info.distribution.days_0_30 + time_info.distribution.days_31_60
        pct_60 = round(within_60 / total * 100, 1)
        summary.append(
            f"Average time to chargeback is {time_info.average_days} days, "
            f"with {pct_60}% filed within 60 days"
        )

    email_count = len([e for e in offenders.by_email if e.chargeback_count >= 3])
    card_count = len([c for c in offenders.by_card_bin if c.chargeback_count >= 3])
    if email_count > 0 or card_count > 0:
        summary.append(
            f"{email_count} email addresses and {card_count} card BINs are repeat "
            f"offenders with 3+ chargebacks each"
        )

    return summary


def analyze_chargebacks(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> ChargebackAnalysisResponse:
    """Perform full chargeback pattern analysis across 5 dimensions."""
    conn = get_connection()
    where, params = _build_date_filter(start_date, end_date)

    row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM chargebacks WHERE {where}", params
    ).fetchone()
    total = row["cnt"]

    # Get date range
    date_row = conn.execute(
        f"""SELECT MIN(chargeback_date) as min_date, MAX(chargeback_date) as max_date
            FROM chargebacks WHERE {where}""",
        params,
    ).fetchone()

    period = {
        "start": start_date or (date_row["min_date"] or ""),
        "end": end_date or (date_row["max_date"] or ""),
    }

    by_country = _analyze_by_country(where, params, total)
    by_category = _analyze_by_category(where, params, total)
    by_reason = _analyze_by_reason_code(where, params, total)
    time_info = _analyze_time_to_chargeback(where, params)
    offenders = _analyze_repeat_offenders(where, params)
    summary = _generate_summary(total, by_country, by_category, by_reason, time_info, offenders)

    return ChargebackAnalysisResponse(
        total_chargebacks=total,
        analysis_period=period,
        by_country=by_country,
        by_product_category=by_category,
        by_reason_code=by_reason,
        time_to_chargeback=time_info,
        repeat_offenders=offenders,
        summary=summary,
    )
