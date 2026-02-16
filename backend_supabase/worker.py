import time
from backend_supabase.auto_categorize import run_auto_categorization


def start_worker():
    print("🚀 AI Worker Started...")

    while True:
        try:
            run_auto_categorization()
        except Exception as e:
            print("❌ Worker error:", e)

        print("😴 Sleeping 10 seconds...\n")
        time.sleep(10)


if __name__ == "__main__":
    start_worker()