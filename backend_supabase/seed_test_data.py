"""Seed test data for ML pipeline training.

Generates:
- Test users
- 24 months of SMS-based transactions with proper schema
- Auto-categorized transactions
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta, date
from supabase import create_client
from dotenv import load_dotenv
import uuid
import random

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


# Fixed category IDs (from seed_merchants.py)
CATEGORIES = {
    "Food & Dining":      "31dd2d93-25f4-43c6-9833-6816d8a1bfce",
    "Shopping":           "b2104a33-0a09-44b1-9026-195e01c73ddc",
    "Transportation":     "1da57196-d4fb-4785-96d1-3fbe7cc34e58",
    "Utilities & Bills":  "429fcded-f706-4576-8858-a4421f57a8b1",
    "Entertainment":      "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d",
    "Health & Fitness":   "4a71ecfa-554a-49f8-8daf-004a99dcda21",
    "Transfer & Wallet":  "fecd0afa-5522-416e-b8b8-c08bbb3fe993",
    "Gaming & Gambling":  "7e8f1234-5a6b-4c7d-8e9f-123456789abc",
    "Others":             "3880903c-bc06-44f1-9eed-da04124feb70",
}

SMS_TEMPLATES = {
    "Zomato": [
        "Rs {amt} debited via UPI to Zomato Media. Food delivery.",
        "Zomato order: {amt} charged to your account.",
    ],
    "Swiggy": [
        "Rs {amt} debited on Swiggy order. Ref: {ref}",
        "Swiggy payment {amt} successful.",
    ],
    "Whole Foods": [
        "Rs {amt} charged at Whole Foods.",
        "Payment of {amt} to Whole Foods received.",
    ],
    "Netflix": [
        "Netflix subscription charge: Rs {amt}",
        "Netflix India charged Rs {amt} to your account.",
    ],
    "Uber": [
        "Rs {amt} debited for Uber ride. Thank you!",
        "Uber trip charged Rs {amt}.",
    ],
    "Electricity": [
        "Electricity board Rs {amt} bill payment received.",
        "Your electricity bill of Rs {amt} has been paid.",
    ],
    "Landlord": [
        "Rent payment Rs {amt} processed.",
        "Monthly rent of Rs {amt} transferred.",
    ],
    "Amazon": [
        "Amazon purchase Rs {amt} charged.",
        "Order placed: Rs {amt} debited from your account.",
    ],
    "Paytm": [
        "Paytm wallet charged Rs {amt}.",
        "Rs {amt} transferred via Paytm.",
    ],
    "Hospital": [
        "Hospital bill payment Rs {amt} received.",
        "Medical charges {amt} processed.",
    ],
    "Salary": [
        "Salary credit Rs {amt} received.",
        "Your monthly salary of Rs {amt} has been credited.",
    ],
}


def generate_test_users() -> list[str]:
    """Get or create test user IDs (use hardcoded UUIDs for reproducibility)."""
    user_ids = [
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "testuser1.example.com")),
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "testuser2.example.com")),
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "testuser3.example.com")),
    ]
    return user_ids


def seed_transactions(user_ids: list[str], months: int = 24):
    """Generate 24 months of SMS-based transactions for each user."""
    now = datetime.now(timezone.utc)
    
    merchants = {
        "Zomato": ("Food & Dining", 30, 80),
        "Swiggy": ("Food & Dining", 20, 100),
        "Whole Foods": ("Shopping", 50, 150),
        "Netflix": ("Entertainment", 10, 20),
        "Uber": ("Transportation", 10, 60),
        "Electricity": ("Utilities & Bills", 80, 200),
        "Landlord": ("Utilities & Bills", 1000, 2000),
        "Amazon": ("Shopping", 50, 300),
        "Paytm": ("Transfer & Wallet", 100, 1000),
        "Hospital": ("Health & Fitness", 200, 1000),
        "Salary": ("Transfer & Wallet", 3000, 5000),
    }
    
    txn_list = []
    categorization_list = []
    
    for user_id in user_ids:
        print(f"Generating transactions for user {user_id[:8]}...")
        for month_back in range(months):
            y = now.year
            m = now.month - month_back
            while m <= 0:
                m += 12
                y -= 1
            
            # Mix of ~30-40 transactions per month
            num_txns = random.randint(25, 40)
            for _ in range(num_txns):
                day = random.randint(1, 28)
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                
                txn_date = datetime(y, m, day, hour, minute, tzinfo=timezone.utc)
                txn_id = str(uuid.uuid4())
                
                # Pick a merchant
                merchant_name = random.choice(list(merchants.keys()))
                category_name, min_amt, max_amt = merchants[merchant_name]
                category_id = CATEGORIES.get(category_name, CATEGORIES["Others"])
                
                # Random amount
                amount = round(random.uniform(min_amt, max_amt), 2)
                
                # Generate SMS text from template
                sms_template = random.choice(SMS_TEMPLATES.get(merchant_name, [f"Payment {merchant_name} Rs {{amt}}"]))
                raw_text = sms_template.format(amt=int(amount), ref=str(uuid.uuid4())[:8].upper())
                
                # Create transaction record (SMS-based)
                txn_record = {
                    "id": txn_id,
                    "user_id": user_id,
                    "raw_text": raw_text,  # This is the primary SMS text
                    "amount": amount,  # REQUIRED: amount must be non-null
                    "timestamp": txn_date.isoformat(),  # REQUIRED: timestamp must be non-null
                    "merchant_name": merchant_name,
                    "created_at": txn_date.isoformat(),
                    "is_processed": True,  # Mark as processed
                }
                txn_list.append(txn_record)
                
                # Create categorization record
                cat_record = {
                    "transaction_id": txn_id,
                    "user_id": user_id,
                    "primary_category_id": category_id,
                }
                categorization_list.append(cat_record)
    
    # Insert transactions in batches
    print(f"\nInserting {len(txn_list)} transactions...")
    for i in range(0, len(txn_list), 100):
        chunk = txn_list[i:i+100]
        try:
            _sb.table("transactions").upsert(chunk, on_conflict=["id"]).execute()
            print(f"  ✓ Inserted transactions {i+1}-{min(i+100, len(txn_list))}")
        except Exception as e:
            print(f"  ⚠ Error: {str(e)[:100]}")
    
    # Insert categorizations in batches
    print(f"\nInserting {len(categorization_list)} categorizations...")
    for i in range(0, len(categorization_list), 100):
        chunk = categorization_list[i:i+100]
        try:
            _sb.table("transaction_categorizations").upsert(chunk, on_conflict=["transaction_id"]).execute()
            print(f"  ✓ Inserted categorizations {i+1}-{min(i+100, len(categorization_list))}")
        except Exception as e:
            print(f"  ⚠ Error: {str(e)[:100]}")
    
    return len(txn_list), len(categorization_list)


def main():
    print("\n=== Seeding Test Data for ML Pipeline ===\n")
    
    user_ids = generate_test_users()
    print(f"Using {len(user_ids)} test users:")
    for uid in user_ids:
        print(f"  - {uid}")
    print()
    
    txn_count, cat_count = seed_transactions(user_ids, months=24)
    
    print(f"\n✓ Seeding complete!")
    print(f"  Transactions: {txn_count}")
    print(f"  Categorizations: {cat_count}")
    print(f"\nNow run:")
    print(f"  python backend_supabase/ml_pipeline.py    # Build ML features")
    print(f"  python backend_supabase/train_forecast.py # Train models")
    print()


if __name__ == "__main__":
    main()
