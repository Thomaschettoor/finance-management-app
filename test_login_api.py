#!/usr/bin/env python3
"""
Test login API with Thomas credentials.
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

TEST_EMAIL = "thomas@gmail.com"
TEST_PASSWORD = "thomas123"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def test_login():
    """Test login with Thomas credentials."""
    print("🔐 Testing login API...")
    print(f"   Email: {TEST_EMAIL}")
    print(f"   Password: {'*' * len(TEST_PASSWORD)}")
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        auth_response = supabase.auth.sign_in_with_password({
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if auth_response.user and auth_response.session:
            print("\n✅ LOGIN SUCCESSFUL!")
            print(f"   User ID: {auth_response.user.id}")
            print(f"   Email: {auth_response.user.email}")
            print(f"   Token: {auth_response.session.access_token[:30]}...")
            return True
        else:
            print("\n❌ LOGIN FAILED: No user or session returned")
            return False
            
    except Exception as e:
        print(f"\n❌ LOGIN FAILED: {e}")
        return False


if __name__ == "__main__":
    test_login()
