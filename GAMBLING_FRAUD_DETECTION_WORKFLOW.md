# Gambling & Fraud Detection - Complete Detailed Workflow

## 📊 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TRANSACTION FLOW                                 │
└─────────────────────────────────────────────────────────────────────────┘

User SMS/UPI Transaction → Database → Auto-categorization → Analytics Pipeline
                                              ↓
                                    [NEW] Gambling Detection
                                    [NEW] Fraud Pattern Detection
                                              ↓
                                      Risk Scoring Update
                                              ↓
                                      Insights Generation
                                              ↓
                                    User Alerts/Dashboards
```

---

## 🔄 **COMPLETE WORKFLOW - STEP BY STEP**

### **PHASE 1: TRANSACTION INGESTION**

#### What Happens:
1. User makes a transaction (SMS/UPI received)
2. Transaction is parsed and stored in `transactions` table
3. Merchant name is extracted (e.g., "Dream11 Pvt Ltd")

#### Database Tables Involved:
```sql
-- Transaction stored here
INSERT INTO transactions (
    id, user_id, amount, merchant_name, 
    transaction_type, timestamp, raw_text
) VALUES (
    'txn-12345', 'user-1', 500.00, 'Dream11',
    'DEBIT', '2026-03-07 23:45:00', 'Rs 500 Dream11 Ref: ABC123'
);
-- Result: 1 new transaction
```

#### Example Transaction:
```
Date: March 7, 2026 11:45 PM
Amount: ₹500
Merchant: Dream11
Type: Debit (Outgoing)
Reference: ABC123456
```

---

### **PHASE 2: GAMBLING DETECTION PIPELINE**

#### **STEP 1: Merchant Matching** 
When the transaction is stored, the gambling detection system checks if the merchant is in the `gambling_merchant_intelligence` table.

#### What Happens:

```python
# gambling_detection_service.py - _is_gambling_merchant()
merchant_name = "Dream11"  # From transaction

# Step 1: Exact match lookup
SELECT * FROM gambling_merchant_intelligence 
WHERE merchant_name ILIKE 'Dream11'
-- Result: Finds match!

{
    "id": "uuid-123",
    "merchant_name": "Dream11",
    "merchant_type": "FANTASY_SPORTS",
    "risk_level": "HIGH",
    "keywords": ["dream", "fantasy"]
}
```

#### Database Check:

```sql
-- Query runs every time a new transaction comes in
SELECT * FROM gambling_merchant_intelligence 
WHERE merchant_name ILIKE '%dream%' 
   OR merchant_name ILIKE '%Dream11%';

-- Matches found: YES ✓
-- Classification: FANTASY_SPORTS, HIGH RISK
```

#### If Match Found:
```
✓ Transaction marked as GAMBLING activity
✓ Stored for behavioral analysis
✓ Added to gambling metrics calculation
```

#### If No Match:
```
✗ Regular transaction
✗ Does not affect gambling analysis
```

---

### **PHASE 3: GAMBLING METRICS COMPUTATION** 

#### Timing: Every ~2000 seconds (background worker)

#### What Happens:

When the analytics worker runs, it computes gambling behavior metrics for each user.

#### **For User 'user-1':**

```python
# Step 1: Detect all gambling transactions (90-day window)
detected_gambling_txns = detect_gambling_transactions('user-1', days=90)

# Pseudo-result:
[
    {
        'transaction_id': 'txn-1',
        'amount': 500,
        'merchant_name': 'Dream11',
        'timestamp': '2026-03-07 23:45:00',
        'gambling_type': 'FANTASY_SPORTS',
        'is_late_night': True  # 11:45 PM = late night
    },
    {
        'transaction_id': 'txn-2',
        'amount': 300,
        'merchant_name': 'MPL',
        'timestamp': '2026-03-06 01:30:00',
        'gambling_type': 'FANTASY_SPORTS',
        'is_late_night': True  # 1:30 AM = late night
    },
    {
        'transaction_id': 'txn-3',
        'amount': 200,
        'merchant_name': 'RummyCircle',
        'timestamp': '2026-03-05 14:20:00',
        'gambling_type': 'CASINO',
        'is_late_night': False  # 2:20 PM = daytime
    }
]
```

#### **Step 2: Calculate Metrics**

```python
# From detect_gambling_transactions() results:
total_gambling_transactions = 3
total_gambling_spend = 500 + 300 + 200 = ₹1000
late_night_count = 2  # Dream11 + MPL

# Get total spending from all transactions (90 days)
total_all_spending = ₹10,000  # From all transactions

# Calculate metrics:
gambling_spend_ratio = 1000 / 10000 = 0.10  # 10% of spending
gambling_frequency_score = 3 / 13 weeks = 0.23  # ~0.23 txns per week
max_gambling_amount = ₹500
```

#### **Step 3: Compute Gambling Risk Score**

```python
# From compute_gambling_metrics() in gambling_detection_service.py
gambling_risk_score = min(100, int(
    gambling_spend_ratio * 40 +          # 0.10 * 40 = 4 points
    min(gambling_frequency_score * 30, 30) +  # 0.23 * 30 = 6.9 points
    min(late_night_count * 5, 20) +      # 2 * 5 = 10 points
    min(unique_merchants * 10, 10)       # 3 merchants * 10 = 10 (capped)
))

gambling_risk_score = 4 + 6.9 + 10 + 10 = 30.9 ≈ 31/100
```

#### **Step 4: Store in Database**

```sql
-- Upsert into user_gambling_behavior
INSERT INTO user_gambling_behavior (
    user_id,
    gambling_spend_ratio,
    gambling_transaction_count,
    last_gambling_transaction,
    max_gambling_amount,
    gambling_frequency_score,
    late_night_gambling_count,
    gambling_risk_score,
    last_updated
) VALUES (
    'user-1',
    0.10,           -- 10% of spending
    3,              -- 3 gambling transactions
    '2026-03-07 23:45:00',  -- Most recent
    500,            -- Largest amount
    0.23,           -- ~0.23 per week
    2,              -- 2 late-night transactions
    31,             -- Gambling risk score
    NOW()
)
ON CONFLICT (user_id) DO UPDATE SET
    gambling_spend_ratio = 0.10,
    gambling_transaction_count = 3,
    gambling_risk_score = 31,
    last_updated = NOW();

-- Result: 1 row inserted/updated in user_gambling_behavior
```

---

### **PHASE 4: FRAUD PATTERN DETECTION**

#### Timing: Every ~2000 seconds (during worker analytics cycle)

#### What Happens:

Simultaneously with gambling metrics, fraud patterns are analyzed.

#### **Pattern 1: HIGH VELOCITY**

```python
# Check for >5 transactions in 1 hour window

transactions_by_hour = {
    '2026-03-07_23': [  # 11 PM hour
        {'amount': 500, 'merchant': 'Dream11'},
        {'amount': 300, 'merchant': 'Amazon'},
        {'amount': 200, 'merchant': 'Zomato'},
        {'amount': 150, 'merchant': 'Uber'},
        {'amount': 100, 'merchant': 'Netflix'},
        {'amount': 50, 'merchant': 'Starbucks'}  # 6 transactions in 1 hour!
    ]
}

# Result: PATTERN DETECTED!
detected_pattern = {
    'pattern_type': 'HIGH_VELOCITY',
    'severity': 'HIGH',
    'detection_details': {
        'window': '2026-03-07_23',
        'transaction_count': 6,
        'total_amount': 1300
    },
    'related_transaction_ids': ['txn-1', 'txn-2', 'txn-3', 'txn-4', 'txn-5', 'txn-6']
}
```

#### **Pattern 2: DUPLICATE PAYMENTS**

```python
# Check for same amount to same merchant within 5 minutes

transactions_sorted = [
    {
        'id': 'txn-100',
        'amount': 999,
        'merchant': 'PokerStars',
        'timestamp': '2026-03-07 20:15:00'
    },
    {
        'id': 'txn-101',
        'amount': 999,  # SAME AMOUNT
        'merchant': 'PokerStars',  # SAME MERCHANT
        'timestamp': '2026-03-07 20:17:30'  # 2.5 minutes later
    }
]

# Time difference = 2.5 minutes (< 5 minutes threshold)
# Result: DUPLICATE PAYMENT DETECTED!

detected_pattern = {
    'pattern_type': 'DUPLICATE_PAYMENTS',
    'severity': 'MEDIUM',
    'detection_details': {
        'amount': 999,
        'merchant': 'PokerStars',
        'time_gap_minutes': 2.5
    },
    'related_transaction_ids': ['txn-100', 'txn-101']
}
```

#### **Pattern 3: AMOUNT ANOMALY**

```python
# Check if transaction is 3x user's average

user_transactions_90days = [
    100, 150, 200, 120, 180, 90, 150, 200, ...
]

average_amount = sum(amounts) / len(amounts) = 150

# New transaction
new_txn = {
    'amount': 5000,  # VERY HIGH!
    'merchant': 'Bet365'
}

# Anomaly check:
is_anomaly = 5000 > (150 * 3) AND 5000 > 1000  # TRUE

multiplier = 5000 / 150 = 33.3x user's average!

detected_pattern = {
    'pattern_type': 'AMOUNT_ANOMALY',
    'severity': 'MEDIUM',
    'detection_details': {
        'transaction_amount': 5000,
        'user_average': 150,
        'multiplier': 33.3
    },
    'related_transaction_ids': ['txn-150']
}
```

#### **Step 4: Store Fraud Patterns**

```sql
-- For each detected pattern
INSERT INTO user_fraud_patterns (
    user_id,
    pattern_type,
    severity,
    detection_details,
    related_transaction_ids,
    detected_at,
    resolved
) VALUES (
    'user-1',
    'HIGH_VELOCITY',
    'HIGH',
    '{"window":"2026-03-07_23","transaction_count":6,"total_amount":1300}',
    ARRAY['txn-1','txn-2','txn-3','txn-4','txn-5','txn-6'],
    NOW(),
    false
);

-- Result: 3 new fraud patterns stored (if all 3 were detected)
```

---

### **PHASE 5: ENHANCED RISK SCORING**

#### Timing: During worker analytics cycle (same time as gambling detection)

#### What Happens:

The existing risk scoring system is enhanced with gambling and fraud factors.

#### **Step 1: Compute Original Risk Factors**

```python
# From analytics_service.py - compute_risk_profile_for_user()

# Expense Volatility (90-day standard deviation)
all_amounts = [100, 150, 200, 120, 180, 90, 150, 200, ...]
expense_volatility = stddev(all_amounts) = 45

# Savings Ratio (last month)
total_credit = ₹50,000
total_debit = ₹40,000
net_savings = 10,000
savings_ratio = 10,000 / 50,000 = 0.20  # 20% savings

# Recurring Burden (fixed expenses per month)
recurring_payments = ₹8,000
recurring_burden_ratio = 8,000 / 50,000 = 0.16  # 16%
```

#### **Step 2: Get Gambling Metrics**

```python
# Call gambling_detection_service
gambling_metrics = compute_gambling_metrics('user-1')

# Result:
gambling_risk_score = 31
gambling_spend_ratio = 0.10
```

#### **Step 3: Get Fraud Risk**

```python
# Call fraud pattern detection
fraud_patterns = detect_fraud_patterns('user-1')

# Count patterns
fraud_pattern_count = 3  # HIGH_VELOCITY + DUPLICATE + AMOUNT_ANOMALY

# Convert to risk score
fraud_risk_score = min(100, 3 * 25) = 75  # 25 points per pattern
```

#### **Step 4: Calculate Enhanced Risk Score**

```python
# Scale components to 0-100
vol_score = min(100, 45) = 45
inv_savings = (1 - 0.20) * 100 = 80  # Low savings = high risk
burden = min(100, 0.16 * 100) = 16

# Base risk (70% weight)
base_risk = 0.3 * 45 + 0.25 * 80 + 0.25 * 16
         = 13.5 + 20 + 4 = 37.5

# Gambling factor (15% weight)
gambling_factor = 0.15 * 31 = 4.65

# Fraud factor (5% weight)
fraud_factor = 0.05 * 75 = 3.75

# TOTAL RISK SCORE
risk_score = base_risk + gambling_factor + fraud_factor
           = 37.5 + 4.65 + 3.75 = 45.9 ≈ 46/100

# Determine risk level
if risk_score < 34:
    risk_level = "LOW"
elif risk_score < 67:
    risk_level = "MODERATE"  # ← User 'user-1' falls here
else:
    risk_level = "HIGH"
```

#### **Step 5: Store Enhanced Risk Profile**

```sql
-- Update user_financial_risk_profile
INSERT INTO user_financial_risk_profile (
    user_id,
    expense_volatility,
    savings_ratio,
    recurring_burden_ratio,
    risk_score,
    risk_level,
    gambling_risk_score,      -- NEW
    fraud_risk_score,         -- NEW
    gambling_spend_ratio      -- NEW
) VALUES (
    'user-1',
    '45.000',
    '0.2000',
    '0.1600',
    46,                        -- Composite score
    'MODERATE',
    31,                        -- NEW: Gambling component
    75,                        -- NEW: Fraud component
    '0.1000'                   -- NEW: Gambling spend ratio
)
ON CONFLICT (user_id) DO UPDATE SET
    risk_score = 46,
    risk_level = 'MODERATE',
    gambling_risk_score = 31,
    fraud_risk_score = 75,
    gambling_spend_ratio = '0.1000';

-- Result: Enhanced risk profile ready
```

---

### **PHASE 6: INSIGHTS GENERATION**

#### Timing: During worker analytics cycle (after risk scoring)

#### What Happens:

The insights engine generates behavioral alerts based on gambling and fraud data.

#### **GAMBLING INSIGHTS**

```python
# From financial_insights_engine.py - generate_insights_for_user()

gambling_metrics = {
    'gambling_spend_ratio': 0.10,
    'gambling_transaction_count': 3,
    'gambling_frequency_score': 0.23,
    'late_night_gambling_count': 2,
    'max_gambling_amount': 500
}

# Check 1: High Spending Alert
if gambling_spend_ratio > 0.10:  # TRUE (exactly at threshold)
    percentage = int(0.10 * 100) = 10
    
    if gambling_spend_ratio > 0.25:
        severity = "CRITICAL"
    else:
        severity = "WARNING"
    
    insight = {
        'insight_type': 'GAMBLING_ALERT',
        'message': 'Gambling spending detected: 10% of total spending on gaming platforms.',
        'severity': 'WARNING'
    }
```

#### **FREQUENCY ALERT**

```python
gambling_frequency = 0.23  # transactions per week

if gambling_frequency > 2:  # FALSE (only 0.23/week)
    # No alert for frequency
    pass
else:
    # No frequency alert this time
    pass
```

#### **LATE NIGHT PATTERN ALERT**

```python
late_night_count = 2

if late_night_count > 5:  # FALSE
    # No alert (only 2 late-night transactions)
    pass
```

#### **AMOUNT ALERT**

```python
max_gambling_amount = 500

if max_gambling_amount > 5000:  # FALSE
    # No alert (only ₹500 max)
    pass
```

#### **FRAUD INSIGHTS**

```python
# From financial_insights_engine.py - fraud alert generation

fraud_patterns = [
    {
        'pattern_type': 'HIGH_VELOCITY',
        'severity': 'HIGH',
        'detection_details': {...}
    },
    {
        'pattern_type': 'DUPLICATE_PAYMENTS',
        'severity': 'MEDIUM',
        'detection_details': {...}
    }
]

# For HIGH_VELOCITY pattern:
insight = {
    'insight_type': 'FRAUD_VELOCITY',
    'message': 'High transaction velocity detected: 6 transactions totaling ₹1300 in 1 hour. Review for unauthorized activity.',
    'severity': 'HIGH'
}

# For DUPLICATE pattern:
insight = {
    'insight_type': 'FRAUD_DUPLICATE',
    'message': 'Duplicate payment detected: ₹999 to PokerStars within 5 minutes. Check for processing errors.',
    'severity': 'MEDIUM'
}
```

#### **STEP 2: Store Insights**

```sql
-- Insert all generated insights
INSERT INTO user_financial_insights (
    user_id,
    insight_type,
    message,
    severity,
    created_at
) VALUES
-- Gambling Alert
('user-1', 'GAMBLING_ALERT', 
 'Gambling spending detected: 10% of total spending on gaming platforms.',
 'WARNING', NOW()),

-- Fraud Velocity Alert
('user-1', 'FRAUD_VELOCITY',
 'High transaction velocity detected: 6 transactions totaling ₹1300 in 1 hour. Review for unauthorized activity.',
 'HIGH', NOW()),

-- Fraud Duplicate Alert
('user-1', 'FRAUD_DUPLICATE',
 'Duplicate payment detected: ₹999 to PokerStars within 5 minutes. Check for processing errors.',
 'MEDIUM', NOW());

-- Result: 3 new insights generated
```

---

## 🔄 **COMPLETE CYCLE TIMELINE**

```
00:00 - Transaction received: User sends ₹500 to Dream11
        └─ Stored in: transactions table
        └─ Merchant: Dream11 identified

00:01-05:00 - Auto-categorization runs
        └─ Transaction categorized
        └─ Stored in: transaction_categorizations table

~30:00 minutes - Worker analytics cycle starts
        ├─ detect_recurring_all()
        ├─ compute_risk_all()
        │   ├─ Original risk calculation ✓
        │   ├─ gambling_detection_service.compute_gambling_metrics() ✓
        │   │   └─ Updated: user_gambling_behavior
        │   ├─ gambling_detection_service.detect_fraud_patterns() ✓
        │   │   └─ Updated: user_fraud_patterns
        │   └─ Enhanced risk_score stored ✓
        │       └─ Updated: user_financial_risk_profile (with gambling + fraud)
        │
        └─ generate_insights_for_user()
            ├─ gambling_detection_service.compute_gambling_metrics()
            ├─ gambling_detection_service.detect_fraud_patterns()
            └─ Insights generated
                └─ Stored: user_financial_insights (GAMBLING_ALERT, FRAUD_VELOCITY, etc.)

~30:05 - Complete! User sees alerts and updated profile
```

---

## 📱 **USER EXPERIENCE - What the User Sees**

### **On Analytics Dashboard:**

```
┌────────────────────────────────────────────┐
│          FINANCIAL RISK PROFILE            │
├────────────────────────────────────────────┤
│ Overall Risk Level: MODERATE               │
│ Risk Score: 46/100                         │
│                                            │
│ Components:                                │
│ • Expense Volatility: 45/100               │
│ • Savings Ratio: 20%                       │
│ • Recurring Burden: 16%                    │
│ • Gambling Risk: 31/100        [NEW]       │
│ • Fraud Risk: 75/100           [NEW]       │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│         GAMBLING BEHAVIOR PROFILE          │
├────────────────────────────────────────────┤
│ Gambling Spend: 10% of total              │
│ Gambling Transactions: 3 in 90 days       │
│ Frequency: ~0.23 per week                 │
│ Late-night Activity: 2 transactions       │
│ Largest Amount: ₹500                      │
└────────────────────────────────────────────┘
```

### **Alerts Section:**

```
⚠️  WARNING: Gambling Spending Detected
    "Gambling spending detected: 10% of total 
     spending on gaming platforms."
    
🚨 HIGH: High Transaction Velocity
    "6 transactions totaling ₹1300 in 1 hour. 
     Review for unauthorized activity."
    
⚠️  MEDIUM: Duplicate Payment
    "Duplicate payment detected: ₹999 to 
     PokerStars within 5 minutes."
```

---

## 💾 **DATABASE STATE AFTER COMPLETE WORKFLOW**

```sql
-- transactions table
SELECT COUNT(*) FROM transactions WHERE user_id = 'user-1';
-- Result: 50+ transactions over 90 days

-- user_gambling_behavior table
SELECT * FROM user_gambling_behavior WHERE user_id = 'user-1';
-- Result:
-- | user_id  | gambling_ratio | count | frequency | risk_score | updated    |
-- | user-1   | 0.10          | 3     | 0.23      | 31         | 2026-03-07 |

-- user_fraud_patterns table
SELECT * FROM user_fraud_patterns WHERE user_id = 'user-1';
-- Result: 3 rows (HIGH_VELOCITY, DUPLICATE_PAYMENTS, AMOUNT_ANOMALY)

-- user_financial_risk_profile table
SELECT * FROM user_financial_risk_profile WHERE user_id = 'user-1';
-- Result:
-- | user_id | risk_score | risk_level | gambling_score | fraud_score | gambling_ratio |
-- | user-1  | 46         | MODERATE   | 31            | 75          | 0.10          |

-- user_financial_insights table
SELECT * FROM user_financial_insights 
WHERE user_id = 'user-1' 
  AND insight_type IN ('GAMBLING_ALERT', 'FRAUD_VELOCITY', 'FRAUD_DUPLICATE');
-- Result: 3 rows with latest insights
```

---

## 🔄 **CONTINUOUS MONITORING**

The system continuously monitors:

```
┌─────────────────────────────────────────────┐
│       BACKGROUND WORKER (Every 30 mins)     │
├─────────────────────────────────────────────┤
│ 1. Check for new transactions               │
│ 2. Detect gambling merchants                │
│ 3. Recalculate gambling metrics             │
│ 4. Detect fraud patterns                    │
│ 5. Update risk scores                       │
│ 6. Generate fresh insights                  │
│ 7. Alert user if thresholds exceeded        │
└─────────────────────────────────────────────┘

Example: If user suddenly has 8 gambling 
transactions in next cycle:
├─ gambling_spend_ratio: 10% → 18%
├─ gambling_risk_score: 31 → 52
├─ overall_risk_score: 46 → 58 (MODERATE → HIGH)
└─ NEW ALERT: "Gambling activity increased significantly"
```

---

## 🎯 **KEY DECISION POINTS IN WORKFLOW**

```
Transaction → Is it gambling merchant?
              ├─ YES → Track in gambling metrics
              └─ NO → Normal transaction

Risk Calculation → Include gambling + fraud?
                   ├─ YES → Enhanced risk score
                   └─ NO → Original risk score

Insights Generation → Alert thresholds exceeded?
                      ├─ YES → Generate CRITICAL/HIGH/WARNING alerts
                      └─ NO → Generate INFO alerts

User Profile → Show gambling metrics?
               ├─ YES (if gambling detected) → Display dashboard
               └─ NO → Hide gambling section
```

---

## ⚡ **PERFORMANCE CHARACTERISTICS**

```
Operation                    Time Taken
─────────────────────────────────────────
Gambling merchant detection  ~10ms (400 merchants)
Compute gambling metrics     ~50ms (90-day scan)
Fraud pattern detection      ~100ms (full month scan)
Risk score calculation       ~5ms
Insights generation          ~30ms
─────────────────────────────────────────
Total per user per cycle     ~200ms
For 1000 users               ~3-4 minutes
```

---

## 📋 **SUMMARY**

The gambling and fraud detection system works through:

1. **Detection**: Merchants matched against gambling database
2. **Metrics**: Behavior patterns computed from transactions
3. **Scoring**: Risk calculated with gambling/fraud factors
4. **Alerts**: Insights generated for user awareness
5. **Monitoring**: Continuous background analysis every ~30 mins
6. **Dashboard**: User sees enhanced risk profile and alerts

The entire system is **non-invasive**, **automatic**, and **integrated** with existing analytics!