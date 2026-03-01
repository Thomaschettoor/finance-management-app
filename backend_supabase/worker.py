"""Worker: runs categorization every 10s, promotion check every 100s."""
import time
from backend_supabase.auto_categorize import run_auto_categorization
from backend_supabase.promotion_service import run_promotion
from backend_supabase.analytics_service import detect_recurring_all, compute_risk_all, upsert_monthly_user_summary
from backend_supabase.financial_insights_engine import generate_insights_for_user
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

CATEGORIZE_INTERVAL_S = 10
PROMOTION_EVERY_N     = 10   # every N categorization cycles (~100s)


def start_worker():
    print("Worker started.")
    cycle = 0
    analytics_cycle = 0
    while True:
        try:
            run_auto_categorization()
        except Exception as e:
            print(f"Categorization error: {e}")

        cycle += 1
        if cycle % PROMOTION_EVERY_N == 0:
            try:
                run_promotion()
            except Exception as e:
                print(f"Promotion error: {e}")

        # run lightweight analytics periodically (every 200 cycles ~2000s)
        analytics_cycle += 1
        if analytics_cycle % 20 == 0:
            try:
                print("Running analytics: recurring detection + risk scoring + monthly summaries")
                detect_recurring_all()
                compute_risk_all()
                # upsert monthly summary for active users (last 30 days)
                users = (_sb.table("users").select("id").execute().data or [])
                from datetime import datetime
                now = datetime.utcnow()
                month_start = datetime(now.year, now.month, 1)
                for u in users:
                    try:
                        upsert_monthly_user_summary(u["id"], month_start.date())
                        generate_insights_for_user(u["id"])
                    except Exception as e:
                        print(f"Analytics user {u['id']} error: {e}")
            except Exception as e:
                print(f"Analytics error: {e}")

        time.sleep(CATEGORIZE_INTERVAL_S)


if __name__ == "__main__":
    start_worker()
