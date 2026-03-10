-- Migration: 006_gambling_and_fraud_detection
-- Adds gambling detection and fraud monitoring to the existing analytics system
-- Extends the current infrastructure without breaking existing functionality

-- ─────────────────────────────────────────────────────────────────
-- STEP 1: Add Gaming & Gambling category to master categories
-- ─────────────────────────────────────────────────────────────────
INSERT INTO master_categories (id, name, description) 
VALUES ('7e8f1234-5a6b-4c7d-8e9f-123456789abc', 'Gaming & Gambling', 'Gambling, betting, gaming platforms, and lottery transactions')
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────
-- STEP 2: Create gambling merchant intelligence
-- Extends existing merchant categorization system
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gambling_merchant_intelligence (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_name     TEXT NOT NULL UNIQUE,
    merchant_type     TEXT NOT NULL CHECK (merchant_type IN 
        ('SPORTS_BETTING', 'FANTASY_SPORTS', 'CASINO', 'POKER', 'LOTTERY', 'GENERAL_GAMING')),
    risk_level        TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    keywords          TEXT[], -- Additional keywords for fuzzy matching
    created_at        TIMESTAMP DEFAULT now(),
    updated_at        TIMESTAMP DEFAULT now()
);

-- Index for fast merchant lookups
CREATE INDEX IF NOT EXISTS idx_gambling_merchant_name ON gambling_merchant_intelligence (merchant_name);
CREATE INDEX IF NOT EXISTS idx_gambling_merchant_type ON gambling_merchant_intelligence (merchant_type);

-- ─────────────────────────────────────────────────────────────────
-- STEP 3: Populate gambling merchant database
-- ─────────────────────────────────────────────────────────────────
INSERT INTO gambling_merchant_intelligence (merchant_name, merchant_type, risk_level, keywords) VALUES
-- Fantasy Sports
('Dream11', 'FANTASY_SPORTS', 'HIGH', ARRAY['dream', 'fantasy']),
('MPL', 'FANTASY_SPORTS', 'HIGH', ARRAY['mobile premier league', 'mpl']),
('FanFight', 'FANTASY_SPORTS', 'MEDIUM', ARRAY['fanfight', 'fan']),
('My11Circle', 'FANTASY_SPORTS', 'MEDIUM', ARRAY['my11', 'circle']),
('BalleBaazi', 'FANTASY_SPORTS', 'MEDIUM', ARRAY['balle', 'baazi']),

-- Sports Betting
('Bet365', 'SPORTS_BETTING', 'HIGH', ARRAY['bet365', 'betting']),
('1xBet', 'SPORTS_BETTING', 'HIGH', ARRAY['1xbet', '1x']),
('Betway', 'SPORTS_BETTING', 'HIGH', ARRAY['betway', 'way']),

-- Casino/Poker
('PokerStars', 'POKER', 'HIGH', ARRAY['poker', 'stars']),
('Adda52', 'POKER', 'HIGH', ARRAY['adda', '52']),
('RummyCircle', 'CASINO', 'MEDIUM', ARRAY['rummy', 'circle']),
('Ace2Three', 'CASINO', 'MEDIUM', ARRAY['ace2three', 'rummy']),
('Junglee Rummy', 'CASINO', 'MEDIUM', ARRAY['junglee', 'rummy']),

-- Lottery
('Playwin', 'LOTTERY', 'MEDIUM', ARRAY['playwin', 'lottery']),
('Rajshree', 'LOTTERY', 'LOW', ARRAY['rajshree', 'lottery']),

-- General Gaming
('WinZO', 'GENERAL_GAMING', 'MEDIUM', ARRAY['winzo', 'games']),
('Paytm First Games', 'GENERAL_GAMING', 'MEDIUM', ARRAY['paytm games', 'first']),
('GetMega', 'GENERAL_GAMING', 'MEDIUM', ARRAY['getmega', 'mega'])

ON CONFLICT (merchant_name) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────
-- STEP 4: Create gambling behavior tracking table
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_gambling_behavior (
    user_id                     UUID PRIMARY KEY,
    gambling_spend_ratio        NUMERIC DEFAULT 0,     -- gambling_spend / total_spend
    gambling_transaction_count  INTEGER DEFAULT 0,
    last_gambling_transaction   TIMESTAMP,
    max_gambling_amount         NUMERIC DEFAULT 0,
    gambling_frequency_score    NUMERIC DEFAULT 0,     -- transactions per week average
    late_night_gambling_count   INTEGER DEFAULT 0,     -- 10PM-6AM transactions
    gambling_risk_score         INTEGER DEFAULT 0,     -- 0-100 gambling-specific risk
    last_updated                TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gambling_behavior_user ON user_gambling_behavior (user_id);
CREATE INDEX IF NOT EXISTS idx_gambling_behavior_risk ON user_gambling_behavior (gambling_risk_score DESC);

-- ─────────────────────────────────────────────────────────────────
-- STEP 5: Create fraud pattern detection table
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_fraud_patterns (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL,
    pattern_type            TEXT NOT NULL CHECK (pattern_type IN 
        ('HIGH_VELOCITY', 'DUPLICATE_PAYMENTS', 'AMOUNT_ANOMALY', 'TIME_ANOMALY', 'MERCHANT_ANOMALY')),
    severity                TEXT NOT NULL DEFAULT 'LOW' CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH')),
    detection_details       JSONB,
    related_transaction_ids TEXT[],
    detected_at             TIMESTAMP DEFAULT now(),
    resolved                BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_fraud_patterns_user ON user_fraud_patterns (user_id);
CREATE INDEX IF NOT EXISTS idx_fraud_patterns_type ON user_fraud_patterns (pattern_type);
CREATE INDEX IF NOT EXISTS idx_fraud_patterns_severity ON user_fraud_patterns (severity);
CREATE INDEX IF NOT EXISTS idx_fraud_patterns_detected ON user_fraud_patterns (detected_at DESC);

-- ─────────────────────────────────────────────────────────────────
-- STEP 6: Extend user_financial_risk_profile for gambling
-- Add gambling-related columns to existing risk profile table
-- ─────────────────────────────────────────────────────────────────
ALTER TABLE user_financial_risk_profile 
ADD COLUMN IF NOT EXISTS gambling_risk_score INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS fraud_risk_score INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS gambling_spend_ratio NUMERIC DEFAULT 0;

-- Update columns as needed
UPDATE user_financial_risk_profile 
SET gambling_risk_score = 0, fraud_risk_score = 0, gambling_spend_ratio = 0 
WHERE gambling_risk_score IS NULL;

-- ─────────────────────────────────────────────────────────────────
-- STEP 7: Add indexes and triggers for new tables
-- ─────────────────────────────────────────────────────────────────

-- Trigger to update timestamps
CREATE OR REPLACE FUNCTION _upd_gambling_behavior_ts()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.last_updated = now(); RETURN NEW; END;
$$;

DROP TRIGGER IF EXISTS trg_gambling_behavior_updated ON user_gambling_behavior;
CREATE TRIGGER trg_gambling_behavior_updated
    BEFORE UPDATE ON user_gambling_behavior
    FOR EACH ROW EXECUTE FUNCTION _upd_gambling_behavior_ts();

-- Trigger to update gambling merchant intelligence timestamps
CREATE OR REPLACE FUNCTION _upd_gambling_merchant_ts()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;

DROP TRIGGER IF EXISTS trg_gambling_merchant_updated ON gambling_merchant_intelligence;
CREATE TRIGGER trg_gambling_merchant_updated
    BEFORE UPDATE ON gambling_merchant_intelligence
    FOR EACH ROW EXECUTE FUNCTION _upd_gambling_merchant_ts();