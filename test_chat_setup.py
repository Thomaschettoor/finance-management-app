#!/usr/bin/env python3
"""
Quick demo script to test the chat API setup
============================================

This script tests the basic connectivity to OpenRouter API to ensure
the setup is working before running the full chat API.
"""

import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

async def test_openrouter_connectivity():
    """Test basic OpenRouter API connectivity."""
    print("🔧 Testing OpenRouter API connectivity...")
    
    api_key = os.getenv("OPENROUTER_KEY")
    if not api_key:
        print("   ❌ OPENROUTER_KEY not found in .env file")
        return False
    
    print(f"   ✅ API key found: {api_key[:10]}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Simple test payload
    payload = {
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",  # Free Zephyr model
        "messages": [
            {
                "role": "user",
                "content": "Hello! Can you respond with just 'API working'?"
            }
        ],
        "max_tokens": 10,
        "temperature": 0.1,
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            print(f"   📨 Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    ai_response = result["choices"][0]["message"]["content"].strip()
                    print(f"   ✅ OpenRouter API working! Response: '{ai_response}'")
                    return True
                else:
                    print(f"   ❌ Unexpected response format: {result}")
                    return False
            else:
                print(f"   ❌ API error: {response.status_code}")
                print(f"   📄 Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"   ❌ Connection error: {e}")
        return False

def test_environment():
    """Test environment setup."""
    print("🔍 Testing environment setup...")
    
    # Check required environment variables
    required_vars = ["SUPABASE_URL", "SUPABASE_KEY", "OPENROUTER_KEY"]
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked_value = f"{value[:10]}..." if len(value) > 10 else value
            print(f"   ✅ {var}: {masked_value}")
        else:
            print(f"   ❌ {var}: Not found")
    print()

async def main():
    """Main demo function."""
    print("🤖 Chat API Setup Test")
    print("=" * 40)
    print()
    
    # Test environment
    test_environment()
    
    # Test OpenRouter
    if await test_openrouter_connectivity():
        print(f"\n🎉 Setup test successful!")
        print(f"\n📝 Next steps:")
        print(f"   1. Start the FastAPI server:")
        print(f"      uvicorn backend_api.main:app --host 0.0.0.0 --port 8000 --reload")
        print(f"   2. Test the chat API:")
        print(f"      python test_chat_api.py")
        print(f"   3. Or use interactive mode:")
        print(f"      python test_chat_api.py interactive")
    else:
        print(f"\n❌ Setup test failed!")
        print(f"\n💡 Troubleshooting:")
        print(f"   1. Check OPENROUTER_KEY in .env file")
        print(f"   2. Verify internet connection")
        print(f"   3. Check OpenRouter API status")

if __name__ == "__main__":
    asyncio.run(main())