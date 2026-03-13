"""
Analytics routes
----------------
GET /api/v1/analytics/summary    — spending breakdown by category for a period
GET /api/v1/analytics/trends     — month-over-month totals per category
"""

from datetime import datetime, timezone, timedelta
from calendar import monthrange
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Query
from supabase import create_client
import os
from dotenv import load_dotenv

from backend_api.auth import get_current_user
from backend_supabase import analytics_service

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _period_bounds(period: str) -> tuple[datetime, datetime]:
    """
    Returns (start, end) datetimes for a named period.

    Supported values:
        last_30_days   — rolling 30 days back from now
        last_90_days   — rolling 90 days back from now
        this_month     — 1st of current month → now
        last_month     — full previous calendar month
    """
    now = datetime.now(timezone.utc)

    if period == "last_30_days":
        return now - timedelta(days=30), now
    elif period == "last_90_days":
        return now - timedelta(days=90), now
    elif period == "this_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif period == "last_month":
        first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_end = first_of_this - timedelta(seconds=1)
        _, last_day = monthrange(last_month_end.year, last_month_end.month)
        last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return last_month_start, first_of_this
    else:
        # Default: last 30 days
        return now - timedelta(days=30), now


def _fetch_categorized_txns(user_id: str, start: datetime, end: datetime) -> list[dict]:
    """
    Fetch transactions with their category assignment for a user within a date window.
    Returns list of {amount, category_id, transaction_date}.
    """
    txn_rows = (
        _sb.table("transactions")
        .select("id, amount, transaction_date, created_at")
        .eq("user_id", user_id)
        .gte("transaction_date", start.isoformat())
        .lte("transaction_date", end.isoformat())
        .execute()
        .data or []
    )
    if not txn_rows:
        return []

    txn_ids = [r["id"] for r in txn_rows]
    cat_rows = (
        _sb.table("transaction_categorizations")
        .select("transaction_id, primary_category_id, prediction_source")
        .in_("transaction_id", txn_ids)
        .not_.is_("primary_category_id", "null")
        .execute()
        .data or []
    )
    cat_map = {c["transaction_id"]: c for c in cat_rows}

    result = []
    for txn in txn_rows:
        cat = cat_map.get(txn["id"])
        if not cat:
            continue
        result.append({
            "amount":           float(txn.get("amount") or 0),
            "category_id":      cat["primary_category_id"],
            "prediction_source": cat["prediction_source"],
            "transaction_date": txn.get("transaction_date") or txn.get("created_at"),
        })
    return result


def _resolve_category_names(category_ids: list[str]) -> dict[str, str]:
    """Return {category_id: category_name} for a list of ids."""
    if not category_ids:
        return {}
    rows = (
        _sb.table("categories")
        .select("id, name")
        .in_("id", list(set(category_ids)))
        .execute()
        .data or []
    )
    return {r["id"]: r["name"] for r in rows}


# ── GET /analytics/summary ────────────────────────────────────────────────────

@router.get("/summary", summary="Spending summary by category")
def spending_summary(
    period: str = Query(
        "last_30_days",
        description="Period: last_30_days | last_90_days | this_month | last_month",
    ),
    user_id: str = Depends(get_current_user),
):
    """
    Returns spending totals grouped by category for the given period.

    Response includes:
    - total_spent       — sum of all categorized transactions
    - category_count    — number of distinct categories used
    - breakdown         — list of {category_id, category_name, total, count, percentage}
      sorted by total descending
    - unclassified_count — how many transactions still lack a confirmed category
    - period_start / period_end
    """
    start, end = _period_bounds(period)
    txns = _fetch_categorized_txns(user_id, start, end)

    # Tally per category
    totals:  dict[str, float] = defaultdict(float)
    counts:  dict[str, int]   = defaultdict(int)
    unclassified = 0

    for t in txns:
        if t["prediction_source"] == "UNCLASSIFIED":
            unclassified += 1
            continue
        totals[t["category_id"]] += t["amount"]
        counts[t["category_id"]] += 1

    grand_total = sum(totals.values())
    names = _resolve_category_names(list(totals.keys()))

    breakdown = sorted(
        [
            {
                "category_id":   cat_id,
                "category_name": names.get(cat_id, "Unknown"),
                "total":         round(total, 2),
                "count":         counts[cat_id],
                "percentage":    round((total / grand_total * 100), 1) if grand_total else 0.0,
            }
            for cat_id, total in totals.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )

    return {
        "period":             period,
        "period_start":       start.isoformat(),
        "period_end":         end.isoformat(),
        "total_spent":        round(grand_total, 2),
        "category_count":     len(breakdown),
        "unclassified_count": unclassified,
        "breakdown":          breakdown,
    }


# ── GET /analytics/trends ─────────────────────────────────────────────────────

@router.get("/trends", summary="Month-over-month spending trends per category")
def spending_trends(
    months: int = Query(3, ge=2, le=12, description="Number of past months to include"),
    user_id: str = Depends(get_current_user),
):
    """
    Returns month-by-month spending totals per category over the last N months.

    Useful for the mobile app to render a bar/line chart.

    Response shape:
    {
        "months": ["2026-01", "2026-02", "2026-03"],
        "series": [
            {
                "category_id":   "...",
                "category_name": "Food & Dining",
                "monthly_totals": [3200.0, 2800.0, 3100.0]
            },
            ...
        ]
    }
    """
    now = datetime.now(timezone.utc)

    # Build month windows (oldest first)
    month_labels = []
    month_windows = []
    for i in range(months - 1, -1, -1):
        # First day of month i months ago
        y = now.year
        m = now.month - i
        while m <= 0:
            m += 12
            y -= 1
        _, last_day = monthrange(y, m)
        mstart = datetime(y, m, 1, tzinfo=timezone.utc)
        mend   = datetime(y, m, last_day, 23, 59, 59, tzinfo=timezone.utc)
        month_labels.append(f"{y}-{m:02d}")
        month_windows.append((mstart, mend))

    # Fetch all transactions covering the full range
    overall_start = month_windows[0][0]
    overall_end   = month_windows[-1][1]
    txns = _fetch_categorized_txns(user_id, overall_start, overall_end)

    # Build {category_id: [total_month_0, total_month_1, ...]}
    series_data: dict[str, list[float]] = defaultdict(lambda: [0.0] * months)

    for t in txns:
        if t["prediction_source"] == "UNCLASSIFIED":
            continue
        try:
            raw = t["transaction_date"]
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            dt = dt.astimezone(timezone.utc)
        except Exception:
            continue
        for idx, (ws, we) in enumerate(month_windows):
            if ws <= dt <= we:
                series_data[t["category_id"]][idx] += t["amount"]
                break

    names = _resolve_category_names(list(series_data.keys()))

    series = [
        {
            "category_id":    cat_id,
            "category_name":  names.get(cat_id, "Unknown"),
            "monthly_totals": [round(v, 2) for v in monthly],
        }
        for cat_id, monthly in sorted(
            series_data.items(),
            key=lambda kv: sum(kv[1]),
            reverse=True,
        )
    ]

    return {"months": month_labels, "series": series}


# New endpoints using precomputed analytics/service layer


@router.get("/risk_score", summary="Financial risk score")
def risk_score(user_id: str = Depends(get_current_user)):
    resp = analytics_service.compute_risk_profile_for_user(user_id)
    # map to requested fields
    return {
        "risk_score": resp.get("risk_score"),
        "risk_level": resp.get("risk_level"),
        "message": f"Your risk level is {resp.get('risk_level')} with score {resp.get('risk_score')}.",
    }


@router.get("/spending_summary", summary="Spending summary (debits only)")
def spending_summary_overview(
    period: str = Query("current_month", description="Currently only current_month supported"),
    user_id: str = Depends(get_current_user),
):
    # reuse category_breakdown logic but sum debits
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now
    txns = _fetch_categorized_txns(user_id, start, end)
    total = sum(t["amount"] for t in txns if t.get("transaction_type") == "DEBIT")
    count = sum(1 for t in txns if t.get("transaction_type") == "DEBIT")
    return {"total_spent": round(total, 2), "transaction_count": count, "period": period}


@router.get("/monthly_forecast", summary="Monthly spending forecast")
def monthly_forecast(user_id: str = Depends(get_current_user)):
    # last 3 months + prediction equal to last month plus simple growth
    data = analytics_service.get_monthly_trend(user_id, 3)
    months = []
    for item in data:
        months.append({"month": item["month"], "actual": item.get("total_debit", 0), "predicted": None})
    # naive prediction: same as last actual
    if months:
        last_val = months[-1]["actual"]
        import datetime as _dt
        y, m = map(int, months[-1]["month"].split("-"))
        # increment month
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
        next_month = f"{y}-{m:02d}"
        months.append({"month": next_month, "actual": None, "predicted": last_val})
    return {"months": months, "prediction_text": "Forecast based on recent trend."}


@router.get("/alerts", summary="Spending alerts")
def spending_alerts(user_id: str = Depends(get_current_user)):
    # simple example: compare this month's debit total to last month's
    now = datetime.now(timezone.utc)
    this_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month = (this_start - timedelta(days=1)).replace(day=1)
    txns_this = _fetch_categorized_txns(user_id, this_start, now)
    txns_last = _fetch_categorized_txns(user_id, last_month, this_start - timedelta(seconds=1))
    total_this = sum(t['amount'] for t in txns_this if t.get('transaction_type') == 'DEBIT')
    total_last = sum(t['amount'] for t in txns_last if t.get('transaction_type') == 'DEBIT')
    alerts = []
    if total_last and total_this > total_last * 1.5:
        alerts.append({"type": "warning", "title": "Spending spike", "message": "Your debit spending this month is more than 50% higher than last month."})
    if total_this < total_last * 0.7:
        alerts.append({"type": "positive", "title": "Spending down", "message": "Good job! Your spending has decreased compared to last month."})
    return {"alerts": alerts}


@router.get("/recommendations", summary="Financial recommendations")
def recommendations(user_id: str = Depends(get_current_user)):
    # placeholder static suggestions
    recs = [
        {"title": "Set a budget", "message": "Consider setting a monthly budget for categories where you overspend."},
        {"title": "Review subscriptions", "message": "Check recurring payments and cancel those you no longer use."},
    ]
    return {"recommendations": recs}
@router.get("/category_breakdown", summary="Category breakdown (precomputed service)")
def category_breakdown(
    start: Optional[str] = Query(None, description="ISO start date"),
    end: Optional[str] = Query(None, description="ISO end date"),
    user_id: str = Depends(get_current_user),
):
    # defaults to last 30 days
    now = datetime.now(timezone.utc)
    if start:
        s = datetime.fromisoformat(start)
    else:
        s = now - timedelta(days=30)
    if end:
        e = datetime.fromisoformat(end)
    else:
        e = now

    resp = analytics_service.get_category_breakdown(user_id, s, e)
    # adapt structure to required shape
    return {"categories": resp.get("categories", [])}


@router.get("/monthly_trend", summary="Monthly trend (precomputed summaries)")
def monthly_trend(
    months: int = Query(3, ge=1, le=36),
    user_id: str = Depends(get_current_user),
):
    resp = analytics_service.get_monthly_trend(user_id, months)
    return {"trend": resp}
