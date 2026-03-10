"""
Gambling Detection Service
-------------------------
Extends the existing analytics system with gambling and fraud detection capabilities.
Integrates seamlessly with the current categorization and risk scoring pipeline.

Key Features:
- Merchant-based gambling detection using gambling_merchant_intelligence
- Behavioral gambling metrics computation
- Fraud pattern detection
- Integration with existing risk profile system

This service works alongside analytics_service.py and financial_insights_engine.py
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def _is_gambling_merchant(merchant_name: str) -> Optional[Dict]:
    """Check if merchant is a gambling platform using gambling_merchant_intelligence."""
    if not merchant_name:
        return None
    
    # Exact match first
    exact_match = (
        _sb.table("gambling_merchant_intelligence")
        .select("*")
        .ilike("merchant_name", merchant_name)
        .execute()
        .data
    )
    
    if exact_match:
        return exact_match[0]
    
    # Fuzzy keyword matching
    all_merchants = _sb.table("gambling_merchant_intelligence").select("*").execute().data or []
    
    merchant_lower = merchant_name.lower()
    for merchant in all_merchants:
        keywords = merchant.get("keywords", [])
        if any(keyword.lower() in merchant_lower for keyword in keywords):
            return merchant
    
    return None


def _is_late_night_transaction(timestamp: str) -> bool:
    """Check if transaction occurred during late night hours (10PM - 6AM)."""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        hour = dt.hour
        return hour >= 22 or hour <= 6
    except:
        return False


def detect_gambling_transactions(user_id: str, days: int = 90) -> List[Dict]:
    """
    Detect gambling transactions for a user within the specified time window.
    Returns list of transactions identified as gambling activity.
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Fetch user transactions
    transactions = (
        _sb.table("transactions")
        .select("id, amount, merchant_name, timestamp, transaction_type")
        .eq("user_id", user_id)
        .eq("transaction_type", "DEBIT")  # Only outgoing transactions
        .gte("timestamp", start_date.isoformat())
        .lte("timestamp", end_date.isoformat())
        .execute()
        .data or []
    )
    
    gambling_transactions = []
    
    for txn in transactions:
        merchant_info = _is_gambling_merchant(txn.get("merchant_name", ""))
        if merchant_info:
            gambling_transactions.append({
                "transaction_id": txn["id"],
                "amount": float(txn.get("amount", 0)),
                "merchant_name": txn.get("merchant_name"),
                "timestamp": txn.get("timestamp"),
                "gambling_type": merchant_info.get("merchant_type"),
                "risk_level": merchant_info.get("risk_level"),
                "is_late_night": _is_late_night_transaction(txn.get("timestamp", ""))
            })
    
    return gambling_transactions


def compute_gambling_metrics(user_id: str) -> Dict:
    """Compute gambling behavior metrics for risk scoring integration."""
    
    # Get gambling transactions from last 90 days
    gambling_txns = detect_gambling_transactions(user_id, days=90)
    
    # Get total spending for ratio calculation
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=90)
    
    all_txns = (
        _sb.table("transactions")
        .select("amount")
        .eq("user_id", user_id)
        .eq("transaction_type", "DEBIT")
        .gte("timestamp", start_date.isoformat())
        .lte("timestamp", end_date.isoformat())
        .execute()
        .data or []
    )
    
    total_spend = sum(float(txn.get("amount", 0)) for txn in all_txns)
    gambling_spend = sum(txn["amount"] for txn in gambling_txns)
    
    # Compute metrics
    gambling_spend_ratio = (gambling_spend / total_spend) if total_spend > 0 else 0
    gambling_transaction_count = len(gambling_txns)
    max_gambling_amount = max([txn["amount"] for txn in gambling_txns], default=0)
    late_night_count = sum(1 for txn in gambling_txns if txn["is_late_night"])
    
    # Calculate frequency score (transactions per week)
    gambling_frequency_score = (len(gambling_txns) / 13) if gambling_txns else 0  # 90 days / 7 days per week ≈ 13 weeks
    
    # Compute gambling-specific risk score
    gambling_risk_score = min(100, int(
        gambling_spend_ratio * 40 +  # Heavy weight on spending ratio
        min(gambling_frequency_score * 30, 30) +  # Frequency capped at 30
        min(late_night_count * 5, 20) +  # Late night gambling
        min(len(set(txn["merchant_name"] for txn in gambling_txns)) * 10, 10)  # Diversity penalty
    ))
    
    return {
        "user_id": user_id,
        "gambling_spend_ratio": gambling_spend_ratio,
        "gambling_transaction_count": gambling_transaction_count,
        "last_gambling_transaction": max([txn["timestamp"] for txn in gambling_txns], default=None),
        "max_gambling_amount": max_gambling_amount,
        "gambling_frequency_score": gambling_frequency_score,
        "late_night_gambling_count": late_night_count,
        "gambling_risk_score": gambling_risk_score
    }


def update_gambling_behavior(user_id: str) -> Dict:
    """Update gambling behavior metrics in the database."""
    metrics = compute_gambling_metrics(user_id)
    
    # Upsert into user_gambling_behavior table
    _sb.table("user_gambling_behavior").upsert(metrics, on_conflict=["user_id"]).execute()
    
    return metrics


def detect_fraud_patterns(user_id: str, days: int = 30) -> List[Dict]:
    """
    Detect potential fraud patterns in user transactions.
    Returns list of detected patterns for alert generation.
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Fetch recent transactions
    transactions = (
        _sb.table("transactions")
        .select("id, amount, merchant_name, timestamp, transaction_type")
        .eq("user_id", user_id)
        .eq("transaction_type", "DEBIT")
        .gte("timestamp", start_date.isoformat())
        .lte("timestamp", end_date.isoformat())
        .order("timestamp")
        .execute()
        .data or []
    )
    
    patterns = []
    
    if len(transactions) < 3:  # Need minimum transactions for pattern detection
        return patterns
    
    # Pattern 1: High velocity transactions (>5 transactions in 1 hour)
    velocity_windows = {}
    for txn in transactions:
        try:
            dt = datetime.fromisoformat(txn["timestamp"].replace('Z', '+00:00'))
            hour_key = dt.strftime('%Y-%m-%d_%H')
            if hour_key not in velocity_windows:
                velocity_windows[hour_key] = []
            velocity_windows[hour_key].append(txn)
        except:
            continue
    
    for window, txns in velocity_windows.items():
        if len(txns) > 5:
            patterns.append({
                "pattern_type": "HIGH_VELOCITY",
                "severity": "HIGH",
                "detection_details": {
                    "window": window,
                    "transaction_count": len(txns),
                    "total_amount": sum(float(t.get("amount", 0)) for t in txns)
                },
                "related_transaction_ids": [t["id"] for t in txns]
            })
    
    # Pattern 2: Duplicate payments (same amount to same merchant within 5 minutes)
    for i, txn in enumerate(transactions[:-1]):
        next_txn = transactions[i+1]
        try:
            dt1 = datetime.fromisoformat(txn["timestamp"].replace('Z', '+00:00'))
            dt2 = datetime.fromisoformat(next_txn["timestamp"].replace('Z', '+00:00'))
            
            time_diff = (dt2 - dt1).total_seconds() / 60  # minutes
            
            if (time_diff <= 5 and 
                txn.get("merchant_name") == next_txn.get("merchant_name") and
                abs(float(txn.get("amount", 0)) - float(next_txn.get("amount", 0))) < 0.01):
                
                patterns.append({
                    "pattern_type": "DUPLICATE_PAYMENTS",
                    "severity": "MEDIUM",
                    "detection_details": {
                        "amount": txn.get("amount"),
                        "merchant": txn.get("merchant_name"),
                        "time_gap_minutes": time_diff
                    },
                    "related_transaction_ids": [txn["id"], next_txn["id"]]
                })
        except:
            continue
    
    # Pattern 3: Amount anomaly (transaction >3x user's average)
    amounts = [float(t.get("amount", 0)) for t in transactions]
    if amounts:
        avg_amount = sum(amounts) / len(amounts)
        for txn in transactions:
            amount = float(txn.get("amount", 0))
            if amount > avg_amount * 3 and amount > 1000:  # Large anomaly threshold
                patterns.append({
                    "pattern_type": "AMOUNT_ANOMALY",
                    "severity": "MEDIUM",
                    "detection_details": {
                        "transaction_amount": amount,
                        "user_average": avg_amount,
                        "multiplier": amount / avg_amount if avg_amount > 0 else 0
                    },
                    "related_transaction_ids": [txn["id"]]
                })
    
    return patterns


def store_fraud_patterns(user_id: str, patterns: List[Dict]) -> None:
    """Store detected fraud patterns in the database."""
    for pattern in patterns:
        pattern_record = {
            "user_id": user_id,
            "pattern_type": pattern["pattern_type"],
            "severity": pattern["severity"],
            "detection_details": pattern["detection_details"],
            "related_transaction_ids": pattern["related_transaction_ids"],
            "detected_at": datetime.now(timezone.utc).isoformat()
        }
        
        _sb.table("user_fraud_patterns").insert(pattern_record).execute()


def run_gambling_and_fraud_analysis_for_user(user_id: str) -> Dict:
    """
    Main function to run complete gambling and fraud analysis for a user.
    This integrates with the existing analytics pipeline.
    """
    
    # Update gambling behavior metrics
    gambling_metrics = update_gambling_behavior(user_id)
    
    # Detect and store fraud patterns
    fraud_patterns = detect_fraud_patterns(user_id)
    if fraud_patterns:
        store_fraud_patterns(user_id, fraud_patterns)
    
    return {
        "user_id": user_id,
        "gambling_metrics": gambling_metrics,
        "fraud_patterns_detected": len(fraud_patterns),
        "analysis_timestamp": datetime.now(timezone.utc).isoformat()
    }


def run_gambling_and_fraud_analysis_all_users() -> List[Dict]:
    """Run gambling and fraud analysis for all users."""
    # Get all active users
    users = (_sb.table("users").select("id").execute().data or [])
    
    results = []
    for user in users:
        try:
            result = run_gambling_and_fraud_analysis_for_user(user["id"])
            results.append(result)
        except Exception as e:
            print(f"Error analyzing user {user['id']}: {str(e)}")
            continue
    
    return results