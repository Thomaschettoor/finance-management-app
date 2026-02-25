"""Train a simple text classifier from a CSV export.

This script supports two modes:
- If the CSV contains a `label` column, use it directly.
- Otherwise, weak-label using `merchant_name` -> category mapping (CATEGORY_MAP)

The produced model is saved to `transaction_model_v1.pkl` in the same folder.
"""
import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.calibration import CalibratedClassifierCV
import joblib

PROJECT_ROOT = os.path.dirname(__file__)
CSV_PATH = os.path.join(PROJECT_ROOT, '..', 'training_datasets', 'transactions_parsed.csv')
REVIEW_CSV = os.path.join(PROJECT_ROOT, '..', 'training_datasets', 'review_export.csv')
OUT_MODEL = os.path.join(PROJECT_ROOT, 'transaction_model_v1.pkl')

# CATEGORY_MAP (name -> id) used in auto_categorize. We invert it to get name labels
from backend_supabase.auto_categorize import CATEGORY_MAP
INVERTED = {v: k for k, v in CATEGORY_MAP.items()}


def weak_label_from_merchant(merchant_name: str):
    if not merchant_name or pd.isna(merchant_name):
        return None
    m = merchant_name.strip().lower()
    # Food & Dining
    if any(k in m for k in ['zomato', 'swiggy', 'domino', 'mcdonald', 'kfc', 'pizza hut', 'burger king', 'restaurant']):
        return 'Food & Dining'
    # Entertainment
    if any(k in m for k in ['netflix', 'bookmyshow', 'book my show', 'spotify', 'hotstar', 'disneyplus',
                             'prime video', 'primevideo', 'amazon prime', 'mxplayer', 'zee5', 'sonyliv']):
        return 'Entertainment'
    # Transport
    if any(k in m for k in ['uber', 'ola', 'rapido', 'indriver', 'irctc', 'railway', 'metro']):
        return 'Transportation'
    # Health
    if any(k in m for k in ['medplus', 'apollo pharmacy', 'netmeds', 'hospital', 'clinic', 'pharmacy']):
        return 'Health & Fitness'
    # Shopping / Groceries
    if any(k in m for k in ['amazon', 'flipkart', 'myntra', 'dmart', 'bigbasket', 'reliance fresh',
                             'nykaa', 'meesho', 'snapdeal']):
        return 'Shopping'
    # Utilities
    if any(k in m for k in ['jio', 'airtel', 'vi', 'vodafone', 'bsnl', 'electricity', 'bescom',
                             'mseb', 'pspcl', 'tneb', 'bses', 'water supply', 'bwssb']):
        return 'Utilities & Bills'
    # Transfer / Wallet / Income
    if any(k in m for k in ['paytm', 'salary', 'payroll', 'phonepay', 'gpay', 'googlepay']):
        return 'Transfer & Wallet'
    return None


def train():
    df = pd.read_csv(CSV_PATH)
    # If review export exists, append it (use normalized_text/raw_text and merchant_name)
    if os.path.exists(REVIEW_CSV):
        df_rev = pd.read_csv(REVIEW_CSV)
        # ensure same columns exist
        for col in ['raw_text','normalized_text','merchant_name','label']:
            if col not in df_rev.columns:
                df_rev[col] = None
        df = pd.concat([df, df_rev], ignore_index=True)

    # Prefer explicit label column if it contains any labels
    if 'label' in df.columns and df['label'].notna().sum() > 0:
        df = df.dropna(subset=['label'])
        if 'normalized_text' in df.columns:
            X = df['normalized_text'].fillna(df['raw_text']).astype(str)
        else:
            X = df['raw_text'].astype(str)
        y = df['label'].astype(str)
    else:
        # Try weak-labeling
        df['weak_label'] = df.get('merchant_name', pd.Series()).apply(weak_label_from_merchant)
        df = df.dropna(subset=['weak_label'])
        if 'normalized_text' in df.columns:
            X = df['normalized_text'].fillna(df['raw_text']).astype(str)
        else:
            X = df['raw_text'].astype(str)
        y = df['weak_label'].astype(str)

    print(f"Training on {len(X)} examples")
    print("Class distribution:\n", y.value_counts().to_string())
    pipeline = make_pipeline(TfidfVectorizer(ngram_range=(1,2), max_features=30000), LogisticRegression(max_iter=1000, class_weight='balanced'))
    clf = CalibratedClassifierCV(pipeline, cv=3)
    clf.fit(X, y)
    joblib.dump(clf, OUT_MODEL)
    print("Saved model to", OUT_MODEL)


if __name__ == '__main__':
    train()
