#!/usr/bin/env python3
"""
Test Chat API with user authentication
=====================================

This script allows you to test the chat API by:
1. Logging in with email and password 
2. Sending a query to the chat API
3. Displaying the AI response about transaction behavior

Usage:
    python test_chat_api.py
    
    Or with arguments:
    python test_chat_api.py --email "thomas@gmail.com" --password "thomas123" --query "How much did I spend on food this month?"
"""

import os
import sys
import argparse
import asyncio
import json
from datetime import datetime
from supabase import create_client
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_BASE_URL = "http://localhost:8000/api/v1"

def print_header():
    """Print a nice header for the test script."""
    print("🤖 Finance Chat API Test")
    print("=" * 50)
    print()

def login_user(email: str, password: str):
    """Login user and return JWT token."""
    print(f"🔐 Logging in user: {email}")
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Sign in with email and password
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user and auth_response.session:
            token = auth_response.session.access_token
            user_id = auth_response.user.id
            print(f"   ✅ Login successful!")
            print(f"   🆔 User ID: {user_id}")
            print(f"   🎫 Token: {token[:20]}...")
            return token, user_id
        else:
            print(f"   ❌ Login failed: No user or session in response")
            return None, None
            
    except Exception as e:
        print(f"   ❌ Login failed: {e}")
        return None, None

async def query_chat_api(token: str, query: str):
    """Send query to chat API and return response."""
    print(f"\n💬 Sending query to chat API...")
    print(f"   📝 Query: {query}")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": query
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"   📡 Calling: POST {API_BASE_URL}/chat/query")
            response = await client.post(
                f"{API_BASE_URL}/chat/query",
                headers=headers,
                json=payload
            )
            
            print(f"   📨 Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                return data
            elif response.status_code == 401:
                print(f"   ❌ Authentication failed - JWT token may be expired")
                return None
            elif response.status_code == 404:
                print(f"   ❌ Chat API endpoint not found - is the FastAPI server running with chat module?")
                return None
            else:
                print(f"   ❌ API error: {response.status_code}")
                print(f"   📄 Response: {response.text}")
                return None
                
    except httpx.ConnectError:
        print(f"   ❌ Connection failed - is the FastAPI server running?")
        print(f"   💡 Start with: uvicorn backend_api.main:app --host 0.0.0.0 --port 8000 --reload")
        return None
    except httpx.TimeoutException:
        print(f"   ❌ Request timeout - AI query took too long")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def print_chat_response(response_data):
    """Print the chat response in a nice format."""
    if not response_data:
        print(f"\n❌ No response data to display")
        return
    
    ai_response = response_data.get("response", "No response")
    context_used = response_data.get("context_used", {})
    
    print(f"\n🎯 AI Response:")
    print(f"{'='*60}")
    print(f"{ai_response}")
    print(f"{'='*60}")
    
    print(f"\n📊 Context Used:")
    print(f"   • Transactions analyzed: {context_used.get('transactions_analyzed', 'N/A')}")
    print(f"   • Period: {context_used.get('period', 'N/A')}")
    print(f"   • Total amount: ₹{context_used.get('total_amount', 0):,.2f}")

def get_user_input():
    """Get user input for email, password, and query."""
    print("📝 Enter your credentials and query:")
    print()
    
    # Default to Thomas's credentials for quick testing
    email = input("Email (press enter for thomas@gmail.com): ").strip()
    if not email:
        email = "thomas@gmail.com"
    
    password = input("Password (press enter for thomas123): ").strip()
    if not password:
        password = "thomas123"
    
    print()
    query = input("Enter your question about transactions: ").strip()
    if not query:
        query = "How much did I spend on food this month?"
        print(f"Using default query: {query}")
    
    return email, password, query

async def main():
    """Main function to run the chat API test."""
    print_header()
    
    parser = argparse.ArgumentParser(description="Test the finance chat API")
    parser.add_argument("--email", help="User email")
    parser.add_argument("--password", help="User password")
    parser.add_argument("--query", help="Query about transactions")
    
    args = parser.parse_args()
    
    # Get credentials and query
    if args.email and args.password and args.query:
        email, password, query = args.email, args.password, args.query
        print(f"📋 Using command line arguments:")
        print(f"   Email: {email}")
        print(f"   Query: {query}")
    else:
        email, password, query = get_user_input()
    
    print()
    
    # Step 1: Login
    token, user_id = login_user(email, password)
    if not token:
        print(f"\n❌ Cannot continue without valid authentication")
        print(f"\n💡 Troubleshooting:")
        print(f"   1. Make sure setup_test_user.py was run successfully")
        print(f"   2. Check credentials are correct")
        print(f"   3. Verify Supabase connection in .env file")
        sys.exit(1)
    
    # Step 2: Query chat API
    response_data = await query_chat_api(token, query)
    if not response_data:
        print(f"\n❌ Failed to get response from chat API")
        sys.exit(1)
    
    # Step 3: Display response
    print_chat_response(response_data)
    
    print(f"\n✅ Chat API test completed successfully!")

def interactive_mode():
    """Run in interactive mode for multiple queries."""
    print_header()
    print("🔄 Interactive Chat Mode")
    print("Enter 'quit' to exit")
    print()
    
    # Get credentials once
    email, password, _ = get_user_input()
    
    # Login once
    token, user_id = login_user(email, password)
    if not token:
        print(f"\n❌ Authentication failed")
        return
    
    print(f"\n💬 You can now ask questions about your transactions!")
    print(f"   Type 'quit' to exit")
    print()
    
    # Query loop
    while True:
        try:
            query = input("Your question: ").strip()
            if query.lower() in ['quit', 'exit', 'q']:
                print(f"👋 Goodbye!")
                break
            
            if not query:
                continue
            
            # Run async query
            response_data = asyncio.run(query_chat_api(token, query))
            if response_data:
                print_chat_response(response_data)
            print()
            
        except KeyboardInterrupt:
            print(f"\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_mode()
    else:
        asyncio.run(main())