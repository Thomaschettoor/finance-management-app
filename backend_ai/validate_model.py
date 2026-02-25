from supabase import create_client
import os
import csv
from dotenv import load_dotenv
from backend_ai.sms_normalizer import normalize_text
from backend_ai.merchant_extractor import extract_merchant
from backend_ai.categorization_engine import predict_transaction
from backend_ai.confidence_calibrator import calibrate_prob
from backend_supabase.auto_categorize import CATEGORY_MAP, RULE_BOOSTING_ENABLED

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

OUT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'training_datasets', 'validation_report.csv'))


def sample_transactions(limit=200):
    # Prefer recent transactions
    resp = supabase.table('transactions').select('*').order('created_at', desc=True).limit(limit).execute()
    return resp.data or []


def run_validation(limit=200):
    txns = sample_transactions(limit=limit)
    rows = []
    hybrid_overrides = 0
    total = len(txns)

    # fetch merchant db for authoritative matches
    mresp = supabase.table('global_merchant_intelligence').select('*').execute()
    merchant_db = mresp.data or []

    for txn in txns:
        tid = txn.get('id')
        raw = txn.get('raw_text') or ''
        norm, meta = normalize_text(raw)
        merchant_name, merchant_id, merchant_score, merchant_meta = extract_merchant(meta.get('merchant_candidate', ''), merchant_db=merchant_db)

        pred = predict_transaction(norm or raw)
        model_conf = float(pred.get('primary_confidence') or 0)
        try:
            calibrated = calibrate_prob(model_conf)
        except Exception:
            calibrated = model_conf

        prediction_source = 'MODEL'
        applied_rule = None
        boosted_primary_id = None
        boosted_primary_conf = None

        if RULE_BOOSTING_ENABLED and merchant_score >= 0.8 and merchant_meta.get('matched_record'):
            rec = merchant_meta.get('matched_record')
            primary_cat = rec.get('primary_category_id')
            cat_conf = float(rec.get('category_confidence') or 0)
            if primary_cat:
                boosted_primary_conf = max(calibrated, cat_conf)
                boosted_primary_id = primary_cat
                prediction_source = 'HYBRID_RULE'
                applied_rule = rec
                hybrid_overrides += 1

        final_category_id = CATEGORY_MAP.get(pred.get('primary'))
        final_confidence = calibrated
        if boosted_primary_id:
            final_category_id = boosted_primary_id
            final_confidence = boosted_primary_conf

        row = {
            'transaction_id': tid,
            'raw_text': raw,
            'normalized_text': norm,
            'merchant_candidate': meta.get('merchant_candidate'),
            'vpa': meta.get('vpa'),
            'merchant_name': merchant_name,
            'merchant_id': merchant_id,
            'merchant_score': merchant_score,
            'model_primary': pred.get('primary'),
            'model_conf': model_conf,
            'model_conf_calibrated': calibrated,
            'prediction_status': pred.get('status'),
            'prediction_source': prediction_source,
            'final_category_id': final_category_id,
        }
        if applied_rule:
            row['applied_rule'] = applied_rule

        rows.append(row)

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, 'w', newline='', encoding='utf-8') as f:
        fieldnames = list(rows[0].keys()) if rows else ['transaction_id','raw_text']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # Print concise summary
    print(f"Validation run: sampled={total}, hybrid_overrides={hybrid_overrides}")
    # top merchants in sample
    from collections import Counter
    merchants = Counter(r['merchant_name'] or 'UNKNOWN' for r in rows)
    print("Top merchants in sample:")
    for m, c in merchants.most_common(10):
        print(f" - {m}: {c}")
    print(f"Report written to {OUT_FILE}")


if __name__ == '__main__':
    run_validation(limit=200)
