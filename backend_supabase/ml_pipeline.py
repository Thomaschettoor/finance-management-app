"""ML dataset builder and small utilities.

Provides a builder that assembles per-user monthly rows into `monthly_ml_dataset`.
This uses existing services (analytics_service) and the Supabase client already
used elsewhere in the codebase.

ENHANCED: Now includes gambling detection and fraud analysis integration.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, date, timedelta
from supabase import create_client
from dotenv import load_dotenv
from typing import Optional
import math
import pandas as pd

from backend_supabase import analytics_service
# Import gambling detection for enhanced risk analysis
try:
    from backend_supabase import gambling_detection_service
except ImportError:
    import gambling_detection_service

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def _match_category_amount(breakdown: dict, patterns: list[str]) -> float:
    """Given category breakdown {name: amount}, return sum for names matching any pattern (case-insensitive).
    Patterns are substrings to match."""
    total = 0.0
    for name, amt in breakdown.items():
        lname = (name or "").lower()
        for p in patterns:
            if p in lname:
                total += float(amt or 0)
                break
    return total


def build_monthly_ml_dataset(last_n_months: int = 24) -> int:
    """Build/refresh `monthly_ml_dataset` for all users for the last N months.

    Returns number of rows upserted.
    """
    users = (_sb.table("users").select("id").execute().data or [])
    if not users:
        # Fallback: get unique user_ids from transactions
        txn_rows = (_sb.table("transactions").select("user_id", distinct=True).execute().data or [])
        users = [{"id": r["user_id"]} for r in txn_rows if r.get("user_id")]
    
    print(f"Found {len(users)} users to process")
    now = datetime.now(timezone.utc)
    months = []
    for i in range(last_n_months - 1, -1, -1):
        y = now.year
        m = now.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append(date(y, m, 1))

    upserted = 0
    for u in users:
        uid = u["id"]
        for m in months:
            # ensure monthly summary exists
            try:
                analytics_service.upsert_monthly_user_summary(uid, m)
            except Exception as e:
                error_msg = str(e)
                if "transaction_date" in error_msg:
                    print(f"  ERROR DETAIL: {error_msg}")
                    import traceback
                    print(f"  Traceback: {traceback.format_exc()}")
                    break
                # Otherwise just warn and continue
                # print(f"  Warning: summary for {uid[:8]} {m}: {str(e)[:60]}")
                pass

            # fetch monthly summary
            row = (_sb.table("monthly_user_summary").select("total_debit, total_credit, savings_ratio, month").eq("user_id", uid).eq("month", m.isoformat()).execute().data or [])
            if not row:
                continue
            r = row[0]
            total_spend = float(r.get("total_debit") or 0)
            total_income = float(r.get("total_credit") or 0)
            savings_ratio = float(r.get("savings_ratio") or 0)

            # category breakdown for the month
            start = datetime(m.year, m.month, 1, tzinfo=timezone.utc)
            if m.month == 12:
                end = datetime(m.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                end = datetime(m.year, m.month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)

            breakdown_resp = analytics_service.get_category_breakdown(uid, start, end)
            # breakdown_resp: {total_spent, categories: [{category_id, amount, percentage}]}
            # resolve category ids -> names
            cat_items = breakdown_resp.get("categories", [])
            # map id->name
            cat_ids = [c["category_id"] for c in cat_items]
            names_map = {}
            if cat_ids:
                cats = (_sb.table("master_categories").select("id, name").in_("id", cat_ids).execute().data or [])
                names_map = {c["id"]: c["name"] for c in cats}

            breakdown_map = {names_map.get(c["category_id"], "Unknown"): float(c.get("amount") or 0) for c in cat_items}

            food_spend = _match_category_amount(breakdown_map, ["food", "grocery", "dining"])
            bills_spend = _match_category_amount(breakdown_map, ["bill", "utility", "rent", "mortgage"])
            entertainment_spend = _match_category_amount(breakdown_map, ["entertain", "movie", "games", "concert"])

            # ensure risk profile exists and read volatility + recurring burden
            try:
                risk = analytics_service.compute_risk_profile_for_user(uid)
                volatility = float(risk.get("expense_volatility") or 0)
                recurring_burden = float(risk.get("recurring_burden_ratio") or 0)
            except Exception:
                volatility = 0.0
                recurring_burden = 0.0

            payload = {
                "user_id": uid,
                "month": m.isoformat(),
                "total_spend": str(round(total_spend, 2)),
                "total_income": str(round(total_income, 2)),
                "food_spend": str(round(food_spend, 2)),
                "bills_spend": str(round(bills_spend, 2)),
                "entertainment_spend": str(round(entertainment_spend, 2)),
                "volatility": str(round(volatility, 4)),
                "recurring_burden": str(round(recurring_burden, 4)),
                "savings_ratio": str(round(savings_ratio, 4)),
            }

            # Create lagged features for proper time-series forecasting
            user_data = (_sb.table("monthly_ml_dataset").select("*").eq("user_id", uid).order("month").execute().data or [])
            if len(user_data) >= 3:  # Need at least 3 months for lagged features
                user_df = pd.DataFrame(user_data)
                user_df = user_df.sort_values('month')
                
                # Calculate lagged features
                latest = user_df.iloc[-1]
                if len(user_df) >= 2:
                    prev_month = user_df.iloc[-2]
                    spending_trend = float(latest.get("total_spend", 0)) - float(prev_month.get("total_spend", 0))
                    income_trend = float(latest.get("total_income", 0)) - float(prev_month.get("total_income", 0))
                else:
                    spending_trend = 0
                    income_trend = 0
                
                # Calculate 3-month average
                if len(user_df) >= 3:
                    recent_3m = user_df.tail(3)
                    avg_spend_3m = recent_3m['total_spend'].astype(float).mean()
                else:
                    avg_spend_3m = float(latest.get("total_spend", 0))
                
                # Add the new proper features
                payload.update({
                    "total_spend_lag1": str(round(float(prev_month.get("total_spend", 0)) if len(user_df) >= 2 else 0, 2)),
                    "total_income_lag1": str(round(float(prev_month.get("total_income", 0)) if len(user_df) >= 2 else 0, 2)), 
                    "spending_trend": str(round(spending_trend, 2)),
                    "income_trend": str(round(income_trend, 2)),
                    "avg_spend_3m": str(round(avg_spend_3m, 2))
                })

            try:
                _sb.table("monthly_ml_dataset").upsert(payload).execute()
                upserted += 1
            except Exception as e:
                # Fallback: try insert then update
                try:
                    _sb.table("monthly_ml_dataset").insert(payload).execute()
                    upserted += 1
                except:
                    try:
                        _sb.table("monthly_ml_dataset").update(payload).eq("user_id", uid).eq("month", m.isoformat()).execute()
                        upserted += 1
                    except:
                        pass  # Log or handle if needed

    return upserted


def run_gambling_and_fraud_analysis_pipeline(user_limit: Optional[int] = None) -> dict:
    """
    Run gambling detection and fraud analysis for all users.
    This extends the existing analytics pipeline with behavioral risk detection.
    """
    print("🎯 Running gambling and fraud analysis pipeline...")
    
    users = (_sb.table("users").select("id").execute().data or [])
    if user_limit:
        users = users[:user_limit]
    
    results = {
        "users_processed": 0,
        "gambling_behaviors_detected": 0,
        "fraud_patterns_detected": 0,
        "errors": 0
    }
    
    for user in users:
        user_id = user["id"]
        try:
            # Run gambling and fraud analysis
            analysis_result = gambling_detection_service.run_gambling_and_fraud_analysis_for_user(user_id)
            
            results["users_processed"] += 1
            
            # Check if gambling behavior was detected
            gambling_metrics = analysis_result.get("gambling_metrics", {})
            if gambling_metrics.get("gambling_transaction_count", 0) > 0:
                results["gambling_behaviors_detected"] += 1
            
            # Track fraud patterns
            fraud_count = analysis_result.get("fraud_patterns_detected", 0)
            if fraud_count > 0:
                results["fraud_patterns_detected"] += fraud_count
                
            print(f"✓ Processed user {user_id[:8]}: {gambling_metrics.get('gambling_transaction_count', 0)} gambling txns, {fraud_count} fraud patterns")
            
        except Exception as e:
            print(f"✗ Error processing user {user_id}: {str(e)}")
            results["errors"] += 1
    
    print(f"\n📊 Gambling & Fraud Analysis Summary:")
    print(f"   Users processed: {results['users_processed']}")
    print(f"   Users with gambling activity: {results['gambling_behaviors_detected']}")
    print(f"   Total fraud patterns detected: {results['fraud_patterns_detected']}")
    print(f"   Errors: {results['errors']}")
    
    return results


if __name__ == "__main__":
    print("🚀 Starting enhanced ML pipeline with gambling & fraud detection...")
    
    # Build monthly ML dataset
    n = build_monthly_ml_dataset(24)
    print(f"✓ Upserted {n} rows into monthly_ml_dataset")
    
    # Run gambling and fraud analysis
    analysis_results = run_gambling_and_fraud_analysis_pipeline()
    
    print(f"\n🎉 Pipeline completed successfully!")
