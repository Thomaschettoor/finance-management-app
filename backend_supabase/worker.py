"""Worker: runs categorization every 10s, promotion check every 100s."""
import time
from backend_supabase.auto_categorize import run_auto_categorization
from backend_supabase.promotion_service import run_promotion

CATEGORIZE_INTERVAL_S = 10
PROMOTION_EVERY_N     = 10   # every N categorization cycles (~100s)


def start_worker():
    print("Worker started.")
    cycle = 0
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

        time.sleep(CATEGORIZE_INTERVAL_S)


if __name__ == "__main__":
    start_worker()
