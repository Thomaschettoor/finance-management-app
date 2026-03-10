"""Worker: runs categorization every 10s, promotion check every 100s, analytics including gambling/fraud detection."""
import time
from backend_supabase.auto_categorize import run_auto_categorization
from backend_supabase.promotion_service import run_promotion
from backend_supabase.analytics_service import detect_recurring_all, compute_risk_all, upsert_monthly_user_summary
from backend_supabase.financial_insights_engine import generate_insights_for_user
# Import gambling detection for enhanced worker analytics
try:
    from backend_supabase import gambling_detection_service
except ImportError:
    import gambling_detection_service

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
                print("Running enhanced analytics: recurring detection + risk scoring + gambling/fraud analysis + monthly summaries")
                detect_recurring_all()
                compute_risk_all()
                
                # upsert monthly summary and run enhanced insights for active users
                users = (_sb.table("users").select("id").execute().data or [])
                from datetime import datetime
                now = datetime.utcnow()
                month_start = datetime(now.year, now.month, 1)
                
                gambling_users = 0
                fraud_patterns = 0
                
                for u in users:
                    try:
                        user_id = u["id"]
                        
                        # Original analytics
                        upsert_monthly_user_summary(user_id, month_start.date())
                        
                        # Enhanced gambling and fraud analysis
                        analysis_result = gambling_detection_service.run_gambling_and_fraud_analysis_for_user(user_id)
                        
                        # Track metrics
                        gambling_metrics = analysis_result.get("gambling_metrics", {})
                        if gambling_metrics.get("gambling_transaction_count", 0) > 0:
                            gambling_users += 1
                        
                        fraud_count = analysis_result.get("fraud_patterns_detected", 0)
                        if fraud_count > 0:
                            fraud_patterns += fraud_count
                        
                        # Generate insights (now includes gambling and fraud alerts)
                        generate_insights_for_user(user_id)
                        
                    except Exception as e:
                        print(f"Enhanced analytics user {user_id} error: {e}")
                        
                print(f"Enhanced analytics completed: {len(users)} users, {gambling_users} with gambling activity, {fraud_patterns} fraud patterns detected")
                        
            except Exception as e:
                print(f"Enhanced analytics error: {e}")

        time.sleep(CATEGORIZE_INTERVAL_S)


if __name__ == "__main__":
    start_worker()
