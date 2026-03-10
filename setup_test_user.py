#!/usr/bin/env python3
"""
Setup test user script for authentication and transaction API testing.

This script:
1. Creates a test user 'thomas' with email 'thomas@gmail.com' in Supabase Auth
2. Adds the user to the users table (if it exists)
3. Creates synthetic transactions for the user
4. Creates transaction categorizations for the transactions

Usage:
    python setup_test_user.py
"""

import os
import sys
import uuid
import random
from datetime import datetime, timezone, timedelta
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
# Note: For user creation, we need service role key. If not available, we'll use regular key
# and provide instructions for manual user creation
supabase = create_client(
    os.getenv("SUPABASE_URL"), 
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_KEY"))
)

# Test user details
TEST_USER_EMAIL = "thomas@gmail.com"
TEST_USER_PASSWORD = "thomas123"  # Simple password for testing
TEST_USER_NAME = "Thomas"

# Fixed category IDs (from the existing project)
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

# SMS templates for generating realistic transaction data
SMS_TEMPLATES = {
    "Zomato": [
        "Rs {amt} debited via UPI to Zomato Media. Food delivery order #ZOM{ref}.",
        "Zomato order: Rs {amt} charged to your account. Ref: {ref}",
    ],
    "Swiggy": [
        "Rs {amt} debited on Swiggy order. Ref: SW{ref}",
        "Swiggy payment Rs {amt} successful for order {ref}.",
    ],
    "Amazon": [
        "Amazon purchase Rs {amt} charged. Order ID: AMZ{ref}",
        "Rs {amt} debited for Amazon.in order. Ref: {ref}",
    ],
    "Uber": [
        "Rs {amt} debited for Uber ride. Trip ID: UBR{ref}. Thank you!",
        "Uber trip charged Rs {amt}. Reference: {ref}",
    ],
    "Netflix": [
        "Netflix subscription charge: Rs {amt}. Ref: NET{ref}",
        "Netflix India charged Rs {amt} to your account.",
    ],
    "Starbucks": [
        "Rs {amt} charged at Starbucks Coffee. Ref: SB{ref}",
        "Payment of Rs {amt} to Starbucks successful.",
    ],
    "Petrol Pump": [
        "Rs {amt} debited at HP Petrol Pump. Ref: HP{ref}",
        "Fuel payment Rs {amt} processed. Station: Shell",
    ],
    "Electricity Board": [
        "Electricity board Rs {amt} bill payment received. Ref: EB{ref}",
        "Your electricity bill of Rs {amt} has been paid.",
    ],
    "Grocery Store": [
        "Rs {amt} charged at Big Bazaar. Ref: BB{ref}",
        "Payment of Rs {amt} to More Megastore successful.",
    ],
    "Movie Theater": [
        "PVR Cinemas Rs {amt} charged. Booking ID: PVR{ref}",
        "Rs {amt} debited for movie tickets. Ref: INOX{ref}",
    ],
}


def create_auth_user():
    """Create a user in Supabase Auth."""
    print(f"🔐 Creating auth user: {TEST_USER_EMAIL}")
    
    try:
        # Try admin operations first (requires service role key)
        try:
            # Check if user already exists
            existing_users = supabase.auth.admin.list_users()
            for user in existing_users:
                if user.email == TEST_USER_EMAIL:
                    print(f"   ✅ User already exists with ID: {user.id}")
                    return str(user.id)
            
            # Create new user using admin API
            user_response = supabase.auth.admin.create_user({
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "email_confirm": True,  # Auto-confirm email for testing
                "user_metadata": {
                    "name": TEST_USER_NAME,
                    "full_name": TEST_USER_NAME,
                }
            })
            
            if user_response and user_response.user:
                user_id = str(user_response.user.id)
                print(f"   ✅ Created user with ID: {user_id}")
                return user_id
                
        except Exception as admin_error:
            print(f"   ⚠️ Admin API not available (need service role key): {admin_error}")
            print(f"   📝 Manual setup required:")
            print(f"      1. Go to your Supabase Dashboard > Authentication > Users")
            print(f"      2. Click 'Add user' and create:")
            print(f"         Email: {TEST_USER_EMAIL}")
            print(f"         Password: {TEST_USER_PASSWORD}")
            print(f"      3. Copy the user ID and paste it below:")
            
            user_id = input("   Enter the user ID: ").strip()
            if user_id and len(user_id) > 10:  # Basic validation
                print(f"   ✅ Using user ID: {user_id}")
                return user_id
            else:
                print(f"   ❌ Invalid user ID provided")
                return None
            
    except Exception as e:
        print(f"   ❌ Failed to create auth user: {e}")
        return None


def add_user_to_users_table(user_id):
    """Add user to the users table if it exists."""
    print(f"👤 Adding user to users table")
    
    try:
        # Check if user already exists in users table
        existing = supabase.table("users").select("id").eq("id", user_id).execute()
        if existing.data:
            print(f"   ✅ User already exists in users table")
            return True
        
        # Try to insert user into users table with required fields
        user_data = {
            "id": user_id,
            "email": TEST_USER_EMAIL,  # Required field
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        result = supabase.table("users").insert(user_data).execute()
        if result.data:
            print(f"   ✅ Added user to users table")
            return True
        else:
            print(f"   ❌ Failed to add user to users table")
            return False
            
    except Exception as e:
        print(f"   ❌ Error adding user to users table: {e}")
        return False


def generate_synthetic_transactions(user_id, num_transactions=50):
    """Generate synthetic transactions for the test user."""
    print(f"💳 Generating {num_transactions} synthetic transactions")
    
    # Define merchants with their categories and typical amount ranges
    merchants_config = {
        "Zomato": ("Food & Dining", 150, 800),
        "Swiggy": ("Food & Dining", 120, 600), 
        "Amazon": ("Shopping", 500, 5000),
        "Uber": ("Transportation", 80, 400),
        "Netflix": ("Entertainment", 199, 799),
        "Starbucks": ("Food & Dining", 200, 500),
        "Petrol Pump": ("Transportation", 1000, 3000),
        "Electricity Board": ("Utilities & Bills", 800, 2500),
        "Grocery Store": ("Shopping", 800, 3000),
        "Movie Theater": ("Entertainment", 200, 800),
    }
    
    transactions = []
    categorizations = []
    
    # Generate transactions over the last 3 months
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=90)
    
    for i in range(num_transactions):
        # Random date within the last 3 months
        days_back = random.randint(0, 90)
        hours_back = random.randint(0, 23)
        minutes_back = random.randint(0, 59)
        
        transaction_date = now - timedelta(
            days=days_back, 
            hours=hours_back, 
            minutes=minutes_back
        )
        
        # Pick random merchant
        merchant_name = random.choice(list(merchants_config.keys()))
        category_name, min_amount, max_amount = merchants_config[merchant_name]
        category_id = CATEGORIES.get(category_name, CATEGORIES["Others"])
        
        # Generate random amount
        amount = round(random.uniform(min_amount, max_amount), 2)
        
        # Generate SMS text
        templates = SMS_TEMPLATES.get(merchant_name, ["Rs {amt} charged to {merchant}. Ref: {ref}"])
        sms_template = random.choice(templates)
        reference_id = str(uuid.uuid4())[:8].upper()
        raw_text = sms_template.format(
            amt=int(amount), 
            ref=reference_id,
            merchant=merchant_name
        )
        
        # Create transaction record
        transaction_id = str(uuid.uuid4())
        transaction = {
            "id": transaction_id,
            "user_id": user_id,
            "raw_text": raw_text,
            "amount": amount,
            "merchant_name": merchant_name,
            "timestamp": transaction_date.isoformat(),  # Use timestamp, not transaction_date
            "created_at": transaction_date.isoformat(),
            "is_processed": True,
        }
        transactions.append(transaction)
        
        # Create categorization record (minimal, like seed_test_data.py)
        categorization = {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "primary_category_id": category_id,
        }
        categorizations.append(categorization)
    
    return transactions, categorizations


def insert_transactions_batch(transactions, categorizations):
    """Insert transactions and categorizations into the database."""
    print(f"📊 Inserting {len(transactions)} transactions into database")
    
    try:
        # Insert transactions in batches
        batch_size = 50
        for i in range(0, len(transactions), batch_size):
            batch = transactions[i:i + batch_size]
            result = supabase.table("transactions").upsert(batch, on_conflict=["id"]).execute()
            print(f"   ✅ Inserted transactions batch {i//batch_size + 1}")
        
        print(f"📈 Inserting {len(categorizations)} categorizations into database")
        
        # Insert categorizations in batches
        for i in range(0, len(categorizations), batch_size):
            batch = categorizations[i:i + batch_size]
            result = supabase.table("transaction_categorizations").upsert(batch, on_conflict=["transaction_id"]).execute()
            print(f"   ✅ Inserted categorizations batch {i//batch_size + 1}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error inserting data: {e}")
        return False


def verify_setup(user_id):
    """Verify the setup by querying the created data."""
    print(f"🔍 Verifying setup for user {user_id}")
    
    try:
        # Check transactions count
        transactions = supabase.table("transactions").select("id").eq("user_id", user_id).execute()
        transaction_count = len(transactions.data) if transactions.data else 0
        print(f"   📊 Found {transaction_count} transactions")
        
        # Check categorizations count
        categorizations = supabase.table("transaction_categorizations").select("transaction_id").eq("user_id", user_id).execute()
        categorization_count = len(categorizations.data) if categorizations.data else 0
        print(f"   📈 Found {categorization_count} categorizations")
        
        # Show a sample transaction
        if transactions.data:
            sample = supabase.table("transactions").select("*").eq("user_id", user_id).limit(1).execute()
            if sample.data:
                tx = sample.data[0]
                print(f"   💳 Sample transaction: {tx.get('merchant_name', 'Unknown')} - Rs {tx.get('amount', 0)}")
        
        return transaction_count > 0 and categorization_count > 0
        
    except Exception as e:
        print(f"   ❌ Error verifying setup: {e}")
        return False


def main():
    """Main function to setup test user and data."""
    print("🚀 Setting up test user 'thomas' for API testing\n")
    
    # Step 1: Create auth user
    user_id = create_auth_user()
    if not user_id:
        print("❌ Failed to create auth user. Exiting.")
        sys.exit(1)
    
    print(f"\n✅ User ID: {user_id}")
    print(f"✅ Email: {TEST_USER_EMAIL}")
    print(f"✅ Password: {TEST_USER_PASSWORD}")
    
    # Step 2: Add to users table (required for foreign key constraint)
    if not add_user_to_users_table(user_id):
        print("\n❌ Failed to add user to users table. Cannot continue.")
        sys.exit(1)
    
    # Step 3: Generate synthetic transactions
    transactions, categorizations = generate_synthetic_transactions(user_id)
    
    # Step 4: Insert data into database
    if insert_transactions_batch(transactions, categorizations):
        print("\n✅ Successfully inserted transaction data")
    else:
        print("\n❌ Failed to insert transaction data")
        sys.exit(1)
    
    # Step 5: Verify setup
    if verify_setup(user_id):
        print("\n🎉 Setup completed successfully!")
        print("\n📋 Test User Credentials:")
        print(f"   Email: {TEST_USER_EMAIL}")
        print(f"   Password: {TEST_USER_PASSWORD}")
        print(f"   User ID: {user_id}")
        print("\n📝 Next steps:")
        print("   1. Use these credentials to test authentication API")
        print("   2. Use the user ID to test transaction APIs")
        print("   3. Test the /api/v1/transactions endpoint")
    else:
        print("\n❌ Setup verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main()