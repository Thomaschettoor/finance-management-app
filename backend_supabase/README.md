# Supabase Schema + Backend Config

## ML Pipeline: Forecasting + SHAP Explainability

### Quick Start

```bash
# 1. Ensure table exists (applied via Supabase SQL editor)
# migrations/005_monthly_ml_dataset.sql

# 2. Build dataset (once you have user transaction data)
python backend_supabase/ml_pipeline.py
# → Populates monthly_ml_dataset with aggregated features

# 3. Train models (linear regression + random forest)
python backend_supabase/train_forecast.py
# → Trains both models, selects best by MAE
# → Persists to backend_supabase/models/best_model.joblib

# 4. Call prediction endpoint
# GET /api/v1/analytics/forecast
# Returns:
# {
#   "predicted_spend": 42500.0,
#   "shap_values": [
#     {"feature": "food_spend", "impact": 2300},
#     {"feature": "volatility", "impact": 1100}
#   ]
# }
```

### Features Table: `monthly_ml_dataset`

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | text | User UUID |
| `month` | date | 1st of month |
| `total_spend` | numeric | Debit sum (expenses) |
| `total_income` | numeric | Credit sum (income) |
| `food_spend` | numeric | Food + groceries |
| `bills_spend` | numeric | Utilities, rent, mortgages |
| `entertainment_spend` | numeric | Movies, games, entertainment |
| `volatility` | numeric | Expense std. deviation (90d) |
| `recurring_burden` | numeric | % of income tied to recurring|
| `savings_ratio` | numeric | (income - expenses) / income |

### Models

- **Linear Regression**: Baseline, interpretable
- **Random Forest**: Non-linear, captures interactions

Best model selected by MAE (mean absolute error) on test set.

### Files

- `ml_pipeline.py` — Dataset builder
- `train_forecast.py` — Model training (outputs `models/best_model.joblib`)
- `analytics_service.py` — Monthly summary & risk profile (used by pipeline)
- (API route in `backend_api/routes/forecast.py`)
