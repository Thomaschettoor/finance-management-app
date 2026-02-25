from supabase import create_client
import os
import csv
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EXPORT_THRESHOLD = float(os.getenv("EXPORT_CONFIDENCE_THRESHOLD", "0.6"))
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "training_datasets", "review_export.csv")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def export_low_confidence(limit=5000):
    # Join transactions and categorizations for low-confidence or REVIEW items
    query = (
        "SELECT t.id, t.user_id, t.raw_text, t.normalized_text, t.merchant_name, tc.primary_confidence, tc.prediction_status "
        "FROM transactions t JOIN transaction_categorizations tc ON tc.transaction_id = t.id "
        f"WHERE tc.primary_confidence < {EXPORT_THRESHOLD} OR tc.prediction_status = 'REVIEW' LIMIT {limit}"
    )
    data = None
    # Try server-side SQL via RPC; fallback to table join if not available
    try:
        if hasattr(supabase, 'rpc'):
            resp = supabase.rpc('sql', { 'q': query }).execute()
            data = resp.data or None
    except Exception:
        data = None

    # Fallback: if direct SQL is not available or returned nothing, fetch via filter (slower)
    if not data:
        resp = supabase.table('transaction_categorizations').select('*,transactions(*)').lt('primary_confidence', EXPORT_THRESHOLD).limit(limit).execute()
        records = resp.data or []
        rows = []
        for r in records:
            t = r.get('transactions') or {}
            rows.append({
                'id': t.get('id'),
                'user_id': t.get('user_id'),
                'raw_text': t.get('raw_text'),
                'normalized_text': t.get('normalized_text'),
                'merchant_name': t.get('merchant_name'),
                'primary_confidence': r.get('primary_confidence'),
                'prediction_status': r.get('prediction_status'),
            })
    else:
        rows = data

    out_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'training_datasets', 'review_export.csv'))
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id','user_id','raw_text','normalized_text','merchant_name','primary_confidence','prediction_status'])
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in writer.fieldnames})

    print(f"Exported {len(rows)} rows to {out_file}")


if __name__ == '__main__':
    export_low_confidence()
