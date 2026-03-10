-- Migration: create monthly_ml_dataset table (materialized view conceptual)
-- Note: This project uses Supabase. If you prefer SQL migration, run this
-- to create a backing table. The python builder can also populate the table.

CREATE TABLE IF NOT EXISTS monthly_ml_dataset (
    user_id text NOT NULL,
    month date NOT NULL,
    total_spend numeric,
    total_income numeric,
    food_spend numeric,
    bills_spend numeric,
    entertainment_spend numeric,
    volatility numeric,
    recurring_burden numeric,
    savings_ratio numeric,
    PRIMARY KEY (user_id, month)
);

-- Optionally create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_monthly_ml_dataset_user ON monthly_ml_dataset (user_id);