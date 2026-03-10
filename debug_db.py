"""Debug database contents to understand why ml_pipeline returns 0 rows."""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("=== Database Diagnostic ===\n")

# Check transaction counts
try:
    result = sb.table("transactions").select("id", count="exact").execute()
    print(f"✓ Transactions: {result.count}")
except Exception as e:
    print(f"✗ Transactions error: {str(e)[:100]}")

# Check categorizations
try:
    result = sb.table("transaction_categorizations").select("transaction_id", count="exact").execute()
    print(f"✓ Categorizations: {result.count}")
except Exception as e:
    print(f"✗ Categorizations error: {str(e)[:100]}")

# Check monthly summaries
try:
    result = sb.table("monthly_user_summary").select("id", count="exact").execute()
    print(f"✓ Monthly summaries: {result.count}")
except Exception as e:
    print(f"✗ Monthly summaries error: {str(e)[:100]}")

# Check ML dataset
try:
    result = sb.table("monthly_ml_dataset").select("user_id", count="exact").execute()
    print(f"✓ ML dataset rows: {result.count}")
except Exception as e:
    print(f"✗ ML dataset error: {str(e)[:100]}")

# Sample transaction
print("\nSample transaction:")
try:
    sample = sb.table("transactions").select("*").limit(1).execute().data
    if sample:
        txn = sample[0]
        print(f"  ID: {txn.get('id')}")
        print(f"  User: {txn.get('user_id')}")
        print(f"  Amount: {txn.get('amount')}")
        print(f"  Timestamp: {txn.get('timestamp')}")
        print(f"  Created: {txn.get('created_at')}")
    else:
        print("  No transactions found")
except Exception as e:
    print(f"  Error: {str(e)[:100]}")

# Sample categorization
print("\nSample categorization:")
try:
    sample = sb.table("transaction_categorizations").select("*").limit(1).execute().data
    if sample:
        cat = sample[0]
        print(f"  Transaction ID: {cat.get('transaction_id')}")
        print(f"  User ID: {cat.get('user_id')}")
        print(f"  Category ID: {cat.get('primary_category_id')}")
    else:
        print("  No categorizations found")
except Exception as e:
    print(f"  Error: {str(e)[:100]}")
