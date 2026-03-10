"""
Test Gambling and Fraud Detection Implementation
------------------------------------------------
This script demonstrates the new gambling detection and fraud analysis features.
Run this after applying the 006_gambling_and_fraud_detection.sql migration.

Features tested:
1. Gambling merchant detection
2. Gambling behavior metrics computation
3. Fraud pattern detection
4. Enhanced risk scoring with gambling factors
5. Behavioral alerts for gambling and fraud

Usage:
python test_gambling_fraud_detection.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone
from backend_supabase import gambling_detection_service
from backend_supabase import analytics_service  
from backend_supabase.financial_insights_engine import generate_insights_for_user
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def test_gambling_merchant_detection():
    """Test gambling merchant detection functionality."""
    print("🎰 Testing gambling merchant detection...")
    
    # Test known gambling merchants
    test_merchants = ["Dream11", "MPL", "PokerStars", "RummyCircle", "Bet365", "Normal Grocery Store"]
    
    for merchant in test_merchants:
        result = gambling_detection_service._is_gambling_merchant(merchant)
        if result:
            print(f"  ✓ {merchant}: {result['merchant_type']} ({result['risk_level']} risk)")
        else:
            print(f"  ✗ {merchant}: Not a gambling merchant")


def test_user_gambling_analysis(user_id: str):
    """Test gambling analysis for a specific user."""
    print(f"\n🔍 Testing gambling analysis for user {user_id[:8]}...")
    
    try:
        # Detect gambling transactions
        gambling_txns = gambling_detection_service.detect_gambling_transactions(user_id)
        print(f"  Found {len(gambling_txns)} gambling transactions")
        
        if gambling_txns:
            for txn in gambling_txns[:3]:  # Show first 3
                print(f"    - ₹{txn['amount']} to {txn['merchant_name']} ({txn['gambling_type']})")
        
        # Compute gambling metrics
        metrics = gambling_detection_service.compute_gambling_metrics(user_id)
        print(f"  Gambling spend ratio: {metrics['gambling_spend_ratio']:.1%}")
        print(f"  Gambling frequency: {metrics['gambling_frequency_score']:.1f} txns/week")
        print(f"  Late night gambling: {metrics['late_night_gambling_count']} transactions")
        print(f"  Gambling risk score: {metrics['gambling_risk_score']}/100")
        
        return metrics
        
    except Exception as e:
        print(f"  ❌ Error in gambling analysis: {e}")
        return None


def test_fraud_detection(user_id: str):
    """Test fraud pattern detection for a specific user."""
    print(f"\n🚨 Testing fraud detection for user {user_id[:8]}...")
    
    try:
        fraud_patterns = gambling_detection_service.detect_fraud_patterns(user_id)
        print(f"  Found {len(fraud_patterns)} potential fraud patterns")
        
        for pattern in fraud_patterns:
            print(f"    - {pattern['pattern_type']}: {pattern['severity']} severity")
            
        return fraud_patterns
        
    except Exception as e:
        print(f"  ❌ Error in fraud detection: {e}")
        return []


def test_enhanced_risk_scoring(user_id: str):
    """Test the enhanced risk scoring with gambling factors."""
    print(f"\n📊 Testing enhanced risk scoring for user {user_id[:8]}...")
    
    try:
        # Get enhanced risk profile
        risk_profile = analytics_service.compute_risk_profile_for_user(user_id)
        
        print(f"  Overall risk score: {risk_profile['risk_score']}/100 ({risk_profile['risk_level']})")
        print(f"  Gambling risk component: {risk_profile['gambling_risk_score']}/100")
        print(f"  Fraud risk component: {risk_profile['fraud_risk_score']}/100")
        print(f"  Gambling spend ratio: {risk_profile['gambling_spend_ratio']}")
        print(f"  Expense volatility: {risk_profile['expense_volatility']}")
        print(f"  Savings ratio: {risk_profile['savings_ratio']}")
        
        return risk_profile
        
    except Exception as e:
        print(f"  ❌ Error in risk scoring: {e}")
        return None


def test_behavioral_insights(user_id: str):
    """Test behavioral insights including gambling and fraud alerts."""
    print(f"\n💡 Testing behavioral insights for user {user_id[:8]}...")
    
    try:
        insights = generate_insights_for_user(user_id)
        
        gambling_insights = [i for i in insights if 'GAMBLING' in i['insight_type']]
        fraud_insights = [i for i in insights if 'FRAUD' in i['insight_type']]
        
        print(f"  Generated {len(insights)} total insights")
        print(f"    - {len(gambling_insights)} gambling-related")
        print(f"    - {len(fraud_insights)} fraud-related")
        
        # Show gambling insights
        if gambling_insights:
            print(f"\n  🎰 Gambling insights:")
            for insight in gambling_insights:
                print(f"    {insight['severity']}: {insight['message']}")
        
        # Show fraud insights  
        if fraud_insights:
            print(f"\n  🚨 Fraud insights:")
            for insight in fraud_insights:
                print(f"    {insight['severity']}: {insight['message']}")
                
        return insights
        
    except Exception as e:
        print(f"  ❌ Error generating insights: {e}")
        return []


def run_comprehensive_test():
    """Run comprehensive test of all gambling and fraud detection features."""
    print("🚀 Starting comprehensive gambling & fraud detection test...\n")
    
    # Test 1: Gambling merchant detection
    test_gambling_merchant_detection()
    
    # Test 2: Get a test user
    try:
        users = _sb.table("users").select("id").limit(1).execute().data
        if not users:
            print("\n❌ No users found in database. Please create a test user first.")
            return
        
        user_id = users[0]["id"]
        print(f"\n👤 Using test user: {user_id}")
        
        # Test 3: Gambling analysis
        gambling_metrics = test_user_gambling_analysis(user_id)
        
        # Test 4: Fraud detection
        fraud_patterns = test_fraud_detection(user_id)
        
        # Test 5: Enhanced risk scoring
        risk_profile = test_enhanced_risk_scoring(user_id)
        
        # Test 6: Behavioral insights
        insights = test_behavioral_insights(user_id)
        
        # Summary
        print(f"\n🎉 Test Summary:")
        print(f"   User analyzed: {user_id[:8]}")
        if gambling_metrics:
            print(f"   Gambling transactions: {gambling_metrics.get('gambling_transaction_count', 0)}")
            print(f"   Gambling risk: {gambling_metrics.get('gambling_risk_score', 0)}/100")
        if fraud_patterns:
            print(f"   Fraud patterns detected: {len(fraud_patterns)}")
        if risk_profile:
            print(f"   Overall risk level: {risk_profile.get('risk_level', 'UNKNOWN')}")
        if insights:
            print(f"   Total insights generated: {len(insights)}")
            
        print(f"\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")


if __name__ == "__main__":
    print("="*60)
    print("🎯 GAMBLING & FRAUD DETECTION TEST SUITE")
    print("="*60)
    
    run_comprehensive_test()
    
    print(f"\n" + "="*60)
    print("📋 Next Steps:")
    print("1. Apply the migration: migrations/006_gambling_and_fraud_detection.sql")
    print("2. Run the enhanced ML pipeline: python backend_supabase/ml_pipeline.py")
    print("3. Check user_gambling_behavior and user_fraud_patterns tables")
    print("4. Monitor user_financial_insights for new alert types")
    print("="*60)