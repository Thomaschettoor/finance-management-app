"""Financial insights engine: generates insights and stores them in DB."""
from datetime import datetime, timezone, timedelta
from collections import Counter
import os
from supabase import create_client
from dotenv import load_dotenv

# Import gambling detection for behavioral alerts
try:
    from . import gambling_detection_service
except ImportError:
    import gambling_detection_service

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def _fetch_categorized_txns(user_id: str, start, end):
    return (
        _sb.table("transactions")
        .select("id, amount, transaction_date, merchant_name, transaction_type")
        .eq("user_id", user_id)
        .gte("transaction_date", start.isoformat())
        .lte("transaction_date", end.isoformat())
        .execute()
        .data or []
    )


def generate_insights_for_user(user_id: str):
    now = datetime.now(timezone.utc)
    last_90 = now - timedelta(days=90)
    txns = _fetch_categorized_txns(user_id, last_90, now)

    if not txns:
        return []

    # 1) Higher than usual spending alert: compare last 7 days vs prior 30 days
    def _to_dt(r):
        try:
            return datetime.fromisoformat(str(r["transaction_date"]).replace("Z", "+00:00"))
        except Exception:
            return None

    now = datetime.now(timezone.utc)
    last_7 = now - timedelta(days=7)
    prior_30 = now - timedelta(days=37)

    sum_last7 = sum(float(r.get("amount") or 0) for r in txns if _to_dt(r) and _to_dt(r) >= last_7)
    sum_prior30 = sum(float(r.get("amount") or 0) for r in txns if _to_dt(r) and prior_30 <= _to_dt(r) < last_7)
    insights = []
    if sum_prior30 and sum_last7 > (sum_prior30 / 4.0) * 1.5:
        msg = f"Spending rose to {round(sum_last7,2)} in last 7 days — {int((sum_last7/(sum_prior30/4.0))*100)}% vs previous average."
        insights.append({"insight_type": "SPENDING_ALERT", "message": msg, "severity": "WARNING"})

    # 2) Evening spending pattern
    hours = [(_to_dt(r).hour if _to_dt(r) else 0) for r in txns]
    evening = sum(1 for h in hours if 18 <= h <= 23)
    if evening > (len(hours) * 0.4):
        insights.append({"insight_type": "EVENING_PATTERN", "message": "Many purchases occur in the evening hours.", "severity": "INFO"})

    # 3) Weekend spike
    weekends = 0
    for r in txns:
        dt = _to_dt(r)
        if not dt:
            continue
        if dt.weekday() >= 5:
            weekends += 1
    if weekends > (len(txns) * 0.35):
        insights.append({"insight_type": "WEEKEND_SPIKE", "message": "Significant spending on weekends.", "severity": "INFO"})

    # 4) Subscription alert — detect recurring merchant with no charges in last 60 days
    merchants = Counter([r.get("merchant_name") for r in txns if r.get("merchant_name")])
    for merchant, cnt in merchants.items():
        # naive: if merchant appeared >=3 times historically but not in last 60 days
        all_txns = (_sb.table("transactions").select("transaction_date").eq("user_id", user_id).eq("merchant_name", merchant).execute().data or [])
        if len(all_txns) >= 3:
            last_dates = sorted([datetime.fromisoformat(str(x["transaction_date"]).replace("Z", "+00:00")) for x in all_txns if x.get("transaction_date")])
            if last_dates and (now - last_dates[-1]).days > 60:
                insights.append({"insight_type": "SUBSCRIPTION_ALERT", "message": f"No recent charge from {merchant} in 60+ days; check subscription.", "severity": "INFO"})

    # 5) Savings opportunity: if savings_ratio low in last month
    # fetch last month summary if present
    last_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    row = (_sb.table("monthly_user_summary").select("savings_ratio").eq("user_id", user_id).eq("month", last_month.date().isoformat()).execute().data or [])
    if row:
        sr = float(row[0].get("savings_ratio") or 0)
        if sr < 0.05:
            insights.append({"insight_type": "SAVINGS_OPPORTUNITY", "message": "Low savings last month. Consider trimming discretionary spend.", "severity": "WARNING"})

    # 6) NEW: Gambling behavior alerts
    try:
        gambling_metrics = gambling_detection_service.compute_gambling_metrics(user_id)
        
        # High gambling spend ratio alert
        gambling_ratio = gambling_metrics.get("gambling_spend_ratio", 0)
        if gambling_ratio > 0.10:  # >10% of spending on gambling
            percentage = int(gambling_ratio * 100)
            if gambling_ratio > 0.25:  # >25% is critical
                insights.append({
                    "insight_type": "GAMBLING_ALERT", 
                    "message": f"High gambling activity: {percentage}% of spending on gaming/betting platforms. Consider reviewing spending habits.",
                    "severity": "CRITICAL"
                })
            else:
                insights.append({
                    "insight_type": "GAMBLING_ALERT", 
                    "message": f"Gambling spending detected: {percentage}% of total spending on gaming platforms.",
                    "severity": "WARNING"
                })
        
        # Frequent gambling transactions
        gambling_count = gambling_metrics.get("gambling_transaction_count", 0)
        gambling_frequency = gambling_metrics.get("gambling_frequency_score", 0)
        if gambling_frequency > 2:  # More than 2 transactions per week on average
            insights.append({
                "insight_type": "GAMBLING_FREQUENCY",
                "message": f"Frequent gambling activity: {gambling_count} transactions in last 90 days (avg {gambling_frequency:.1f}/week).",
                "severity": "WARNING"
            })
        
        # Late night gambling pattern
        late_night_count = gambling_metrics.get("late_night_gambling_count", 0)
        if late_night_count > 5:  # >5 late night gambling transactions
            insights.append({
                "insight_type": "GAMBLING_PATTERN",
                "message": f"Late-night gambling detected: {late_night_count} gambling transactions between 10PM-6AM. Consider setting spending limits.",
                "severity": "WARNING"
            })
            
        # High gambling amount spike
        max_gambling = gambling_metrics.get("max_gambling_amount", 0)
        if max_gambling > 5000:  # Large single gambling transaction
            insights.append({
                "insight_type": "GAMBLING_AMOUNT",
                "message": f"Large gambling transaction detected: ₹{max_gambling:.0f}. Monitor for impulsive spending patterns.",
                "severity": "WARNING"
            })
            
    except Exception as e:
        print(f"Warning: Gambling insights failed for user {user_id}: {e}")

    # 7) NEW: Fraud pattern alerts
    try:
        fraud_patterns = gambling_detection_service.detect_fraud_patterns(user_id)
        
        for pattern in fraud_patterns:
            pattern_type = pattern.get("pattern_type", "")
            severity = pattern.get("severity", "LOW")
            details = pattern.get("detection_details", {})
            
            if pattern_type == "HIGH_VELOCITY":
                transaction_count = details.get("transaction_count", 0)
                total_amount = details.get("total_amount", 0)
                insights.append({
                    "insight_type": "FRAUD_VELOCITY",
                    "message": f"High transaction velocity detected: {transaction_count} transactions totaling ₹{total_amount:.0f} in 1 hour. Review for unauthorized activity.",
                    "severity": severity
                })
            elif pattern_type == "DUPLICATE_PAYMENTS":
                amount = details.get("amount", 0)
                merchant = details.get("merchant", "Unknown")
                insights.append({
                    "insight_type": "FRAUD_DUPLICATE",
                    "message": f"Duplicate payment detected: ₹{amount} to {merchant} within 5 minutes. Check for processing errors.",
                    "severity": severity
                })
            elif pattern_type == "AMOUNT_ANOMALY":
                amount = details.get("transaction_amount", 0)
                multiplier = details.get("multiplier", 0)
                insights.append({
                    "insight_type": "FRAUD_ANOMALY",
                    "message": f"Unusual transaction amount: ₹{amount:.0f} is {multiplier:.1f}x your average spending. Verify transaction authenticity.",
                    "severity": severity
                })
                
    except Exception as e:
        print(f"Warning: Fraud insights failed for user {user_id}: {e}")

    # persist insights
    out = []
    for ins in insights:
        payload = {"user_id": user_id, "insight_type": ins["insight_type"], "message": ins["message"], "severity": ins.get("severity", "INFO")}
        _sb.table("user_financial_insights").insert(payload).execute()
        out.append(payload)

    return out
