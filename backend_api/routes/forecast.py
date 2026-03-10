"""Forecasting endpoints: predict next-month spend and return SHAP explanations."""
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client
from dotenv import load_dotenv
import os
from joblib import load
import pandas as pd
import shap

from backend_api.auth import get_current_user
from backend_supabase import ml_pipeline

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

router = APIRouter(prefix="/analytics", tags=["Forecasting"])


def _load_model(path: str = "backend_supabase/models/fixed_model.joblib"):
    if not os.path.exists(path):
        raise FileNotFoundError("Fixed model not found; run fix_data_leakage.py first")
    meta = load(path)
    return meta


@router.get("/forecast", summary="Predict next month spending with SHAP explanation")
def forecast_next_month(user_id: str = Depends(get_current_user)):
    """Predict next month's spending using the fixed time-series model."""
    
    # Ensure dataset exists for user
    try:
        ml_pipeline.build_monthly_ml_dataset(12)
    except Exception as e:
        print(f"Warning: Could not rebuild ML dataset: {e}")

    # Get user's monthly data
    rows = (_sb.table("monthly_ml_dataset").select("*").eq("user_id", user_id).execute().data or [])
    if not rows:
        raise HTTPException(status_code=404, detail="No monthly ML data for user")

    df = pd.DataFrame(rows)
    
    # Convert and sort by month
    df["month"] = pd.to_datetime(df["month"])
    df = df.sort_values("month")
    
    # Need at least 2 months for lag features
    if len(df) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 months of data for forecasting")
    
    # Load model
    try:
        model_data = _load_model()
        model = model_data["model"]
        feature_cols = model_data["features"]
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Trained model not found; please train model first")

    # Create time-series features for the user
    df_sorted = df.sort_values(['user_id', 'month']).copy()
    
    # Create lag features
    df_sorted['total_spend_lag1'] = df_sorted['total_spend'].shift(1)
    df_sorted['total_spend_lag2'] = df_sorted['total_spend'].shift(2)
    df_sorted['total_income_lag1'] = df_sorted['total_income'].shift(1)
    df_sorted['food_spend_lag1'] = df_sorted['food_spend'].shift(1)
    df_sorted['bills_spend_lag1'] = df_sorted['bills_spend'].shift(1)
    df_sorted['entertainment_spend_lag1'] = df_sorted['entertainment_spend'].shift(1)
    df_sorted['savings_ratio_lag1'] = df_sorted['savings_ratio'].shift(1)
    
    # Create trend features
    df_sorted['spending_trend'] = df_sorted['total_spend'] - df_sorted['total_spend_lag1']
    df_sorted['income_trend'] = df_sorted['total_income'] - df_sorted['total_income_lag1']
    
    # Create rolling average
    df_sorted['avg_spend_3m'] = df_sorted['total_spend'].rolling(3, min_periods=1).mean()
    
    # Get latest row with features
    latest = df_sorted.iloc[-1]
    
    # Check if we have the required lag features
    if pd.isna(latest['total_spend_lag1']):
        raise HTTPException(status_code=400, detail="Insufficient data for lag features")
    
    # Prepare feature vector
    feature_vector = []
    for feature in feature_cols:
        value = latest[feature]
        if pd.isna(value):
            value = 0.0
        feature_vector.append(value)
    
    # Make prediction
    try:
        prediction = model.predict([feature_vector])[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")

    # Generate SHAP explanation
    shap_values = []
    try:
        # Use TreeExplainer for RandomForest
        explainer = shap.TreeExplainer(model)
        shap_vals = explainer.shap_values([feature_vector])[0]
        
        for feature, shap_val in zip(feature_cols, shap_vals):
            shap_values.append({
                "feature": feature,
                "impact": float(shap_val),
                "value": float(latest[feature]) if not pd.isna(latest[feature]) else 0.0
            })
            
    except Exception as e:
        print(f"SHAP explanation failed: {e}")
        # Return basic feature importance if SHAP fails
        for feature in feature_cols:
            shap_values.append({
                "feature": feature,
                "impact": 0.0,
                "value": float(latest[feature]) if not pd.isna(latest[feature]) else 0.0
            })
    
    # Calculate change from last month
    last_month_spend = latest['total_spend']
    change_amount = prediction - last_month_spend
    change_percent = (change_amount / last_month_spend) * 100 if last_month_spend > 0 else 0
    
    return {
        "predicted_spend": float(prediction),
        "last_month_spend": float(last_month_spend),
        "change_amount": float(change_amount),
        "change_percent": float(change_percent),
        "shap_values": shap_values,
        "model_info": {
            "mae": model_data.get("mae", 0),
            "mape": model_data.get("mape", 0),
            "features_count": len(feature_cols)
        }
    }
