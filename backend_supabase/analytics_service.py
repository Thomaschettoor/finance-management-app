"""Analytics service: precompute summaries, recurring detection, risk scoring."""
from datetime import datetime, timezone, timedelta, date
from collections import defaultdict
import math
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def _fetch_categorized_txns(user_id: str, start: datetime, end: datetime) -> list[dict]:
    rows = (
        _sb.table("transactions")
        .select("id, amount, transaction_date, transaction_type, merchant_name, created_at")
        .eq("user_id", user_id)
        .gte("transaction_date", start.isoformat())
        .lte("transaction_date", end.isoformat())
        .execute()
        .data or []
    )
    if not rows:
        return []
    txn_ids = [r["id"] for r in rows]
    cats = (
        _sb.table("transaction_categorizations")
        .select("transaction_id, primary_category_id")
        .in_("transaction_id", txn_ids)
        .not_.is_("primary_category_id", "null")
        .execute()
        .data or []
    )
    cat_map = {c["transaction_id"]: c["primary_category_id"] for c in cats}
    out = []
    for r in rows:
        cid = cat_map.get(r["id"])
        if not cid:
            continue
        out.append({
            "id": r["id"],
            "amount": float(r.get("amount") or 0),
            "category_id": cid,
            "transaction_type": r.get("transaction_type"),
            "merchant_name": r.get("merchant_name"),
            "transaction_date": r.get("transaction_date") or r.get("created_at"),
        })
    return out


def upsert_monthly_user_summary(user_id: str, month: date) -> None:
    """Compute and upsert monthly summary for `month` (month is a date on 1st).

    month: a `date` representing the first day of the month to compute.
    """
    start = datetime(month.year, month.month, 1, tzinfo=timezone.utc)
    if month.month == 12:
        end = datetime(month.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
    else:
        end = datetime(month.year, month.month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)

    txns = _fetch_categorized_txns(user_id, start, end)
    total_debit = 0.0
    total_credit = 0.0
    total_transactions = 0
    for t in txns:
        amt = t["amount"]
        if t.get("transaction_type") == "DEBIT":
            total_debit += amt
        else:
            total_credit += amt
        total_transactions += 1

    net_savings = total_credit - total_debit
    savings_ratio = (net_savings / total_credit) if total_credit else 0

    payload = {
        "user_id": user_id,
        "month": start.date().isoformat(),
        "total_debit": str(round(total_debit, 2)),
        "total_credit": str(round(total_credit, 2)),
        "net_savings": str(round(net_savings, 2)),
        "total_transactions": total_transactions,
        "savings_ratio": str(round(savings_ratio, 4)),
    }

    # upsert using unique (user_id, month)
    _sb.table("monthly_user_summary").upsert(payload, on_conflict=["user_id", "month"]).execute()


def get_category_breakdown(user_id: str, start: datetime, end: datetime) -> dict:
    txns = _fetch_categorized_txns(user_id, start, end)
    totals = defaultdict(float)
    for t in txns:
        totals[t["category_id"]] += t["amount"]
    grand = sum(totals.values())
    categories = [
        {"category_id": cid, "amount": round(amount, 2), "percentage": round((amount / grand * 100), 1) if grand else 0.0}
        for cid, amount in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return {"total_spent": round(grand, 2), "categories": categories}


def get_monthly_trend(user_id: str, last_n_months: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    results = []
    for i in range(last_n_months - 1, -1, -1):
        y = now.year
        m = now.month - i
        while m <= 0:
            m += 12
            y -= 1
        month_start = date(y, m, 1)
        upsert_monthly_user_summary(user_id, month_start)
        # fetch summary
        row = (
            _sb.table("monthly_user_summary")
            .select("total_debit, total_credit, net_savings, total_transactions, savings_ratio, month")
            .eq("user_id", user_id)
            .eq("month", month_start.isoformat())
            .execute()
            .data or []
        )
        if row:
            r = row[0]
            results.append({"month": r["month"], "total_debit": float(r["total_debit"] or 0)})
        else:
            results.append({"month": month_start.isoformat(), "total_debit": 0.0})
    return results


def _stddev(data: list[float]) -> float:
    if not data:
        return 0.0
    mean = sum(data) / len(data)
    var = sum((x - mean) ** 2 for x in data) / len(data)
    return math.sqrt(var)


def detect_recurring_for_user(user_id: str, lookback_days: int = 365) -> list[dict]:
    """Detect recurring payment patterns for a user and upsert into `recurring_transactions`.

    Returns list of detected patterns.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    txns = _fetch_categorized_txns(user_id, start, end)
    # group by (merchant_name, category)
    buckets = defaultdict(list)
    for t in txns:
        key = (t.get("merchant_name") or "unknown", t.get("category_id"))
        buckets[key].append(t)

    results = []
    for (merchant, category), items in buckets.items():
        if len(items) < 3:
            continue
        # sort by date
        dates = []
        amounts = []
        for it in sorted(items, key=lambda x: x["transaction_date"]):
            try:
                dt = datetime.fromisoformat(str(it["transaction_date"]).replace("Z", "+00:00"))
            except Exception:
                continue
            dates.append(dt)
            amounts.append(it["amount"])
        if len(dates) < 3:
            continue
        intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
        mean_interval = sum(intervals) / len(intervals)
        sd_interval = _stddev(intervals)
        amt_mean = sum(amounts) / len(amounts)
        amt_sd = _stddev(amounts)

        # simple heuristics
        if sd_interval <= 3 and (amt_sd / (amt_mean or 1)) < 0.2:
            next_expected = dates[-1] + timedelta(days=round(mean_interval))
            confidence = max(0.0, 1.0 - (sd_interval / (mean_interval or 1) * 0.5))
            payload = {
                "user_id": user_id,
                "category_id": category,
                "merchant_name": merchant,
                "avg_amount": str(round(amt_mean, 2)),
                "recurrence_interval_days": int(round(mean_interval)),
                "next_expected_date": next_expected.date().isoformat(),
                "confidence_score": str(round(confidence, 3)),
            }
            # upsert by (user_id, merchant_name)
            _sb.table("recurring_transactions").upsert(payload, on_conflict=["user_id", "merchant_name"]).execute()
            results.append(payload)

    return results


def detect_recurring_all(lookback_days: int = 365):
    users = (_sb.table("users").select("id").execute().data or [])
    for u in users:
        detect_recurring_for_user(u["id"], lookback_days=lookback_days)


def compute_risk_profile_for_user(user_id: str) -> dict:
    # 90-day window for volatility
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)
    txns = _fetch_categorized_txns(user_id, start, end)
    amounts = [t["amount"] for t in txns if t.get("transaction_type") == "DEBIT"]
    expense_volatility = _stddev(amounts)

    # savings_ratio from last month summary
    now = datetime.now(timezone.utc)
    last_month = date(now.year, now.month, 1)
    row = (
        _sb.table("monthly_user_summary").select("savings_ratio, total_credit").eq("user_id", user_id).eq("month", last_month.isoformat()).execute().data or []
    )
    savings_ratio = float(row[0]["savings_ratio"]) if row else 0.0

    # recurring burden = sum of recurring avg_amount per month / total_credit
    recs = (_sb.table("recurring_transactions").select("avg_amount").eq("user_id", user_id).execute().data or [])
    recurring_burden = sum(float(r.get("avg_amount") or 0) for r in recs)
    total_credit = float(row[0]["total_credit"]) if row else 0.0
    recurring_burden_ratio = (recurring_burden / total_credit) if total_credit else 0.0

    # risk score: 40% volatility (scaled), 30% inverse savings, 30% recurring burden
    # scale components to 0-100
    vol_score = min(100, expense_volatility)
    inv_savings = (1 - savings_ratio) * 100
    burden = min(100, recurring_burden_ratio * 100)
    risk = int(round(0.4 * vol_score + 0.3 * inv_savings + 0.3 * burden))
    if risk < 34:
        level = "LOW"
    elif risk < 67:
        level = "MODERATE"
    else:
        level = "HIGH"

    payload = {
        "user_id": user_id,
        "expense_volatility": str(round(expense_volatility, 3)),
        "savings_ratio": str(round(savings_ratio, 4)),
        "recurring_burden_ratio": str(round(recurring_burden_ratio, 4)),
        "risk_score": risk,
        "risk_level": level,
    }
    _sb.table("user_financial_risk_profile").upsert(payload, on_conflict=["user_id"]).execute()
    return payload


def compute_risk_all():
    users = (_sb.table("users").select("id").execute().data or [])
    out = []
    for u in users:
        out.append(compute_risk_profile_for_user(u["id"]))
    return out
