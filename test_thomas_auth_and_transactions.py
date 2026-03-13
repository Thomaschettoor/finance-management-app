#!/usr/bin/env python3
"""
Test authentication and transaction API for user Thomas.

This script demonstrates:
1. Logging in with Thomas's credentials to get a JWT token
2. Using the JWT token to fetch Thomas's transactions
3. Displaying transaction data

Usage:
    python test_thomas_auth_and_transactions.py
"""

import os
import requests
import json
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test user credentials (from setup_test_user.py)
TEST_EMAIL = "thomas@gmail.com"
TEST_PASSWORD = "thomas123"

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# API endpoints (assuming FastAPI is running on localhost:8000)
API_BASE_URL = "http://localhost:8000/api/v1"
AUTH_LOGIN_URL = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"

def login_user():
    """Login user using Supabase Auth API and return JWT token."""
    print("🔐 Logging in user...")
    
    try:
        # Login using Supabase Auth API
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Sign in with email and password
        auth_response = supabase.auth.sign_in_with_password({
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if auth_response.user and auth_response.session:
            token = auth_response.session.access_token
            user_id = auth_response.user.id
            print(f"   ✅ Login successful!")
            print(f"   📧 Email: {auth_response.user.email}")
            print(f"   🆔 User ID: {user_id}")
            # print full token so you can copy it for Swagger/verify
            print(f"   🎫 Token: {token}")
            return token, user_id
        else:
            print(f"   ❌ Login failed: No user or session in response")
            return None, None
            
    except Exception as e:
        print(f"   ❌ Login failed: {e}")
        return None, None


def test_transactions_api(token):
    """Test the transactions API with the JWT token."""
    print(f"\n📊 Testing transactions API...")
    
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Test GET /transactions endpoint
        print(f"   📡 Calling GET {API_BASE_URL}/transactions")
        response = requests.get(f"{API_BASE_URL}/transactions", headers=headers, timeout=10)
        
        print(f"   📨 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            transactions = data.get("transactions", [])
            print(f"   ✅ Found {len(transactions)} transactions")
            print(f"   📄 Page: {data.get('page', 'N/A')}, Per page: {data.get('per_page', 'N/A')}")
            
            # Show sample transactions
            if transactions:
                print(f"\n   💳 Sample transactions:")
                for i, txn in enumerate(transactions[:5]):  # Show first 5
                    amount = txn.get("amount", 0)
                    merchant = txn.get("merchant_name", "Unknown")
                    date = txn.get("transaction_date", txn.get("created_at", "Unknown"))
                    category_id = txn.get("category_id", "Uncategorized")
                    category_name = txn.get("category_name") or ""
                    
                    # Format date nicely
                    try:
                        if date != "Unknown":
                            parsed_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
                            formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M")
                        else:
                            formatted_date = date
                    except:
                        formatted_date = date
                    
                    print(f"      {i+1}. {merchant} - ₹{amount} ({formatted_date}) [{category_name or category_id}]")
            else:
                print(f"   ⚠️ No transactions found")
                
        elif response.status_code == 401:
            print(f"   ❌ Authentication failed - check JWT token")
            print(f"   📄 Response: {response.text}")
        elif response.status_code == 404:
            print(f"   ❌ API endpoint not found - is the FastAPI server running?")
            print(f"   💡 Make sure FastAPI is running on {API_BASE_URL}")
        else:
            print(f"   ❌ API call failed")
            print(f"   📄 Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection failed - is the FastAPI server running?")
        print(f"   💡 Start the server with: uvicorn backend_api.main:app --host 0.0.0.0 --port 8000")
    except requests.exceptions.Timeout:
        print(f"   ❌ Request timeout")
    except Exception as e:
        print(f"   ❌ Error: {e}")


def test_single_transaction_api(token, user_id):
    """Test getting a single transaction."""
    print(f"\n🎯 Testing single transaction API...")
    try:
        # First get a transaction ID from the list
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(f"{API_BASE_URL}/transactions?per_page=1", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            transactions = data.get("transactions", [])
            if transactions:
                transaction_id = transactions[0]["id"]
                
                # Test GET single transaction
                print(f"   📡 Calling GET {API_BASE_URL}/transactions/{transaction_id}")
                single_response = requests.get(f"{API_BASE_URL}/transactions/{transaction_id}", headers=headers, timeout=10)
                
                if single_response.status_code == 200:
                    txn = single_response.json()
                    print(f"   ✅ Single transaction fetched successfully")
                    print(f"   💳 {txn.get('merchant_name', 'Unknown')} - ₹{txn.get('amount', 0)}")
                else:
                    print(f"   ❌ Single transaction API failed: {single_response.status_code}")
            else:
                print(f"   ⚠️ No transactions to test with")
        else:
            print(f"   ❌ Could not get transactions list for single transaction test")
    except Exception as e:
        print(f"   ❌ Error testing single transaction: {e}")


def test_sms_ingest_api(token):
    """Submit a dummy SMS to the ingest API and ensure it accepts it."""
    print(f"\n📩 Testing SMS ingest API...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "sms_text": "INR 123.45 debited from ABC card at TESTMERCHANT",
        "sender": "TESTBANK",
        "timestamp": "2026-03-12T05:00:00Z"
    }
    try:
        resp = requests.post(f"{API_BASE_URL}/sms/ingest", headers=headers, json=payload, timeout=10)
        print(f"   📨 Response status: {resp.status_code}")
        print(f"   body: {resp.text}")
    except Exception as e:
        print(f"   ❌ Error calling SMS ingest: {e}")
            
    except Exception as e:
        print(f"   ❌ Error testing single transaction: {e}")


def test_direct_database_query():
    """Test direct database query as fallback."""
    print(f"\n🗃️ Testing direct database query (fallback)...")


def test_categories_api(token):
    """Test the categories endpoint to list all categories."""
    print(f"\n📁 Testing categories API...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.get(f"{API_BASE_URL}/categories", headers=headers, timeout=10)
        print(f"   📨 Response status: {resp.status_code}")
        print(f"   body: {resp.text}")
    except Exception as e:
        print(f"   ❌ Error calling categories API: {e}")
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Query transactions directly from database
        result = supabase.table("transactions").select("id, amount, merchant_name, timestamp").eq("user_id", "4a246b13-1840-43e4-b9ad-82faba38da61").limit(5).execute()
        
        if result.data:
            print(f"   ✅ Found {len(result.data)} transactions in database")
            for txn in result.data:
                print(f"      • {txn.get('merchant_name', 'Unknown')} - ₹{txn.get('amount', 0)}")
        else:
            print(f"   ⚠️ No transactions found in database")
            
    except Exception as e:
        print(f"   ❌ Database query failed: {e}")


def main():
    """Main test function."""
    print("🧪 Testing Thomas authentication and transaction API")
    print("=" * 60)
    
    # Step 1: Login
    token, user_id = login_user()
    if not token:
        print("\n❌ Cannot continue without valid authentication")
        print("\n💡 Troubleshooting:")
        print("   1. Make sure setup_test_user.py was run successfully")
        print("   2. Check Supabase credentials in .env file")
        print("   3. Verify user exists in Supabase Dashboard")
        return
    
    # Step 2: Test transactions API
    test_transactions_api(token)
    
    # Step 3: Test single transaction API
    if user_id:
        test_single_transaction_api(token, user_id)

    # Step 4: Test SMS ingestion (should create a new transaction)
    test_sms_ingest_api(token)

    # Step 5: Test categories API
    test_categories_api(token)
    
    # Step 6: Test direct database query as fallback
    test_direct_database_query()
    
    print(f"\n✅ Testing completed!")
    print(f"\n📝 Summary:")
    print(f"   • Authentication: ✅ Working")
    print(f"   • JWT Token: ✅ Generated")
    print(f"   • User ID: {user_id}")
    print(f"   • Next step: Start FastAPI server to test transaction endpoints")
    print(f"\n🚀 To start the API server:")
    print(f"   cd {os.getcwd()}")
    print(f"   uvicorn backend_api.main:app --host 0.0.0.0 --port 8000 --reload")


if __name__ == "__main__":
    main()