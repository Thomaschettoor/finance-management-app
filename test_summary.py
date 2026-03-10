"""Test upsert_monthly_user_summary to see actual error."""
import os
import sys
from datetime import date
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from backend_supabase import analytics_service

# Get a test user_id
from supabase import create_client
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
users = sb.table("transactions").select("user_id").limit(1).execute().data
if users:
    test_user_id = users[0]["user_id"]
    print(f"Testing with user: {test_user_id}")
    
    try:
        result = analytics_service.upsert_monthly_user_summary(test_user_id, date(2026, 1, 1))
        print(f"✓ Success: {result}")
    except Exception as e:
        print(f"✗ Error: {e}")
else:
    print("No users found!")
