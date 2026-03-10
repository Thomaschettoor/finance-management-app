"""
Chat routes
-----------
POST /api/v1/chat/query    — Chat with AI about transaction behavior
"""

import os
import json
from typing import Dict, List, Any
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import httpx

from supabase import create_client
from dotenv import load_dotenv

from backend_api.auth import get_current_user

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

router = APIRouter(prefix="/chat", tags=["Chat"])

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Updated to new model per user request
MODEL_NAME = "nvidia/nemotron-3-nano-30b-a3b:free"  # New free model


class ChatQueryRequest(BaseModel):
    query: str


class ChatQueryResponse(BaseModel):
    response: str
    context_used: Dict[str, Any]


def get_user_transaction_summary(user_id: str) -> Dict[str, Any]:
    """Fetch user transaction data and create a summary for AI context."""
    try:
        # Get recent transactions (last 90 days)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=90)
        
        # Fetch transactions
        transactions = (
            _sb.table("transactions")
            .select("id, amount, merchant_name, timestamp, created_at, raw_text")
            .eq("user_id", user_id)
            .gte("timestamp", start_date.isoformat())
            .order("timestamp", desc=True)
            .limit(200)  # Limit to avoid token overflow
            .execute()
            .data or []
        )
        
        if not transactions:
            return {
                "total_transactions": 0,
                "message": "No transactions found in the last 90 days"
            }
        
        # Get transaction IDs for categorizations
        transaction_ids = [t["id"] for t in transactions]
        
        # Fetch categorizations
        categorizations = (
            _sb.table("transaction_categorizations")
            .select("transaction_id, primary_category_id")
            .in_("transaction_id", transaction_ids)
            .execute()
            .data or []
        )
        
        cat_map = {c["transaction_id"]: c.get("primary_category_id") for c in categorizations}
        
        # Get category names
        unique_category_ids = list(set(filter(None, cat_map.values())))
        category_names = {}
        if unique_category_ids:
            categories = (
                _sb.table("categories")
                .select("id, name")
                .in_("id", unique_category_ids)
                .execute()
                .data or []
            )
            category_names = {c["id"]: c["name"] for c in categories}
        
        # Analyze transactions
        total_amount = sum(float(t.get("amount", 0)) for t in transactions)
        spending_by_category = {}
        merchant_frequency = {}
        
        for txn in transactions:
            amount = float(txn.get("amount", 0))
            merchant = txn.get("merchant_name", "Unknown")
            category_id = cat_map.get(txn["id"])
            category_name = category_names.get(category_id, "Uncategorized")
            
            # Group by category
            if category_name not in spending_by_category:
                spending_by_category[category_name] = {"amount": 0, "count": 0}
            spending_by_category[category_name]["amount"] += amount
            spending_by_category[category_name]["count"] += 1
            
            # Count merchant frequency
            merchant_frequency[merchant] = merchant_frequency.get(merchant, 0) + 1
        
        # Get top merchants and categories
        top_merchants = sorted(merchant_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
        top_categories = sorted(
            [(cat, data["amount"]) for cat, data in spending_by_category.items()], 
            key=lambda x: x[1], reverse=True
        )[:5]
        
        return {
            "total_transactions": len(transactions),
            "total_amount": total_amount,
            "avg_transaction": total_amount / len(transactions) if transactions else 0,
            "period": "Last 90 days",
            "spending_by_category": spending_by_category,
            "top_merchants": top_merchants,
            "top_categories": top_categories,
            "recent_transactions": transactions[:10]  # Last 10 for context
        }
        
    except Exception as e:
        return {
            "error": f"Failed to fetch transaction data: {str(e)}",
            "total_transactions": 0
        }


def create_ai_context(user_data: Dict[str, Any], query: str) -> str:
    """Create context string for AI model."""
    if "error" in user_data:
        return f"""
You are a personal finance assistant. The user asked: "{query}"

However, there was an error retrieving their transaction data: {user_data['error']}

Please apologize for the technical issue and suggest they try again later or contact support.
"""
    
    if user_data["total_transactions"] == 0:
        return f"""
You are a personal finance assistant. The user asked: "{query}"

The user has no transaction data available in the last 90 days. Please let them know that you need transaction data to provide personalized financial insights and suggest they check back once they have some transactions recorded.
"""
    
    # Format transaction data for AI
    context = f"""
You are a personal finance assistant analyzing a user's spending behavior. Answer their question based on the following transaction data:

USER QUERY: "{query}"

TRANSACTION SUMMARY ({user_data['period']}):
- Total transactions: {user_data['total_transactions']}
- Total amount spent: ₹{user_data['total_amount']:,.2f}
- Average per transaction: ₹{user_data['avg_transaction']:,.2f}

SPENDING BY CATEGORY:
"""
    
    for category, data in user_data['spending_by_category'].items():
        percentage = (data['amount'] / user_data['total_amount']) * 100 if user_data['total_amount'] > 0 else 0
        context += f"- {category}: ₹{data['amount']:,.2f} ({data['count']} transactions, {percentage:.1f}%)\n"
    
    context += f"""
TOP MERCHANTS:
"""
    for merchant, count in user_data['top_merchants']:
        context += f"- {merchant}: {count} transactions\n"
    
    context += f"""
RECENT TRANSACTIONS (sample):
"""
    for txn in user_data['recent_transactions'][:5]:
        timestamp = txn.get('timestamp', txn.get('created_at', 'Unknown'))
        try:
            if timestamp != 'Unknown':
                parsed_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_date = parsed_date.strftime("%Y-%m-%d")
            else:
                formatted_date = timestamp
        except:
            formatted_date = timestamp
            
        context += f"- {txn.get('merchant_name', 'Unknown')}: ₹{txn.get('amount', 0)} ({formatted_date})\n"
    
    context += f"""
Please provide a helpful, personalized response about their spending behavior. Be specific about the data you analyzed and give actionable insights when possible. Keep the response conversational and under 300 words.
"""
    
    return context


async def query_openrouter_ai(context: str) -> str:
    """Send query to OpenRouter AI and get response."""
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenRouter API key not configured"
        )
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": context
            }
        ],
        "max_tokens": 500,
        "temperature": 0.7,
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"OpenRouter API error: {response.status_code} - {response.text}"
                )
            
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No response from AI model"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Request to AI service timed out"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error communicating with AI service: {str(e)}"
        )


@router.post("/query", summary="Chat with AI about transaction behavior", response_model=ChatQueryResponse)
async def chat_query(
    request: ChatQueryRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Chat with AI about user's transaction behavior and spending patterns.
    
    The AI will analyze the user's recent transactions and provide insights
    based on their query about spending habits, patterns, or financial behavior.
    """
    try:
        # Get user transaction data
        user_data = get_user_transaction_summary(user_id)
        
        # Create context for AI
        ai_context = create_ai_context(user_data, request.query)
        
        # Query OpenRouter AI
        ai_response = await query_openrouter_ai(ai_context)
        
        # Prepare response with context info
        context_summary = {
            "transactions_analyzed": user_data.get("total_transactions", 0),
            "period": user_data.get("period", "N/A"),
            "total_amount": user_data.get("total_amount", 0),
        }
        
        return ChatQueryResponse(
            response=ai_response,
            context_used=context_summary
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat query: {str(e)}"
        )