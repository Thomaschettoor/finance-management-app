"""
Transaction Categorization Service - Pure Rule-Based Architecture

Flow per transaction:
  1. Normalize SMS -> extract merchant_candidate
  2. Lookup candidate in confident_merchants
     (exact: merchant_id | merchant_name | aliases array, then fuzzy >= 0.80)
  3. Match    -> assign primary_category_id + confidence_score  (CONFIDENT_MERCHANT)
     No match -> primary_category_id = NULL  (UNCLASSIFIED) -> feed learning pool
  4. Upsert transaction_categorizations
  5. Mark is_processed = True

NO ML. NO keyword heuristics. NO model inference.
"""
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()

from backend_ai.sms_normalizer import normalize_text
from backend_ai.merchant_extractor import extract_merchant
from backend_supabase.behavior_suggestion_engine import generate_suggestions

BATCH_SIZE = 50
CONFIDENT_MATCH_THRESHOLD = 0.80

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

CATEGORY_MAP = {
    "Food & Dining":      "31dd2d93-25f4-43c6-9833-6816d8a1bfce",
    "Shopping":           "b2104a33-0a09-44b1-9026-195e01c73ddc",
    "Transportation":     "1da57196-d4fb-4785-96d1-3fbe7cc34e58",
    "Utilities & Bills":  "429fcded-f706-4576-8858-a4421f57a8b1",
    "Entertainment":      "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d",
    "Health & Fitness":   "4a71ecfa-554a-49f8-8daf-004a99dcda21",
    "Transfer & Wallet":  "fecd0afa-5522-416e-b8b8-c08bbb3fe993",
    "Others":             "3880903c-bc06-44f1-9eed-da04124feb70",
    "Education":          "00bbd2d8-7f0b-4f01-b481-3d81aae5c813",
    "Gifts & Donations":  "18e662e7-5ab7-4482-94e3-777d81a20c68",
    "Subscriptions":      "18f7fb6a-8fe8-46fa-8765-8680064b8655",
    "Financial Services": "2e0c0c8b-b2f1-41fe-bda1-8e8e984ea13e",
    "Travel & Lodging":   "308f79a8-204d-4cad-ac56-ed0f191e3937",
    "Personal Care":      "8af77e68-fb27-4a54-9e0a-cdaa779dbbae",
}


def _nk(t):
    return t.strip().lower() if t else ""


def _lookup_confident_merchant(candidate, confident_db):
    if not candidate or not confident_db:
        return None
    c = _nk(candidate)
    for rec in confident_db:
        if c == _nk(rec.get("merchant_id")):
            return rec
        if c == _nk(rec.get("merchant_name")):
            return rec
        for alias in (rec.get("aliases") or []):
            if alias and c == _nk(alias):
                return rec
    # fuzzy fallback
    _, _, score, meta = extract_merchant(candidate, merchant_db=confident_db)
    if score >= CONFIDENT_MATCH_THRESHOLD and meta.get("matched_record"):
        return meta["matched_record"]
    return None


def _add_to_learning_pool(candidate, user_id):
    if not candidate:
        return
    mid = _nk(candidate).replace(" ", "_")
    mname = candidate.strip()
    try:
        rows = (supabase.table("global_merchant_learning")
                .select("id,total_reports,total_unique_users")
                .eq("merchant_id", mid).limit(1).execute().data or [])
        if rows:
            supabase.table("global_merchant_learning").update({
                "total_reports":      rows[0]["total_reports"] + 1,
                "last_aggregated_at": "now()",
            }).eq("merchant_id", mid).execute()
        else:
            supabase.table("global_merchant_learning").insert({
                "merchant_id":        mid,
                "merchant_name":      mname,
                "total_reports":      1,
                "total_unique_users": 1,
                "last_aggregated_at": "now()",
            }).execute()
    except Exception as e:
        print(f"Warning: learning pool error for {mname!r}: {e}")


def run_auto_categorization():
    txns = (supabase.table("transactions")
            .select("*").eq("is_processed", False).limit(BATCH_SIZE)
            .execute().data or [])
    print(f"Found {len(txns)} transactions to categorize")
    if not txns:
        return

    # cache per batch
    confident_db = supabase.table("confident_merchants").select("*").execute().data or []

    for txn in txns:
        raw_text = txn.get("raw_text")
        if not raw_text:
            continue
        txn_id  = txn["id"]
        user_id = txn["user_id"]

        normalized_text, parsing_meta = normalize_text(raw_text)
        merchant_candidate = parsing_meta.get("merchant_candidate", "")

        matched = _lookup_confident_merchant(merchant_candidate, confident_db)

        if matched:
            primary_cat_id    = matched["primary_category_id"]
            confidence        = float(matched.get("confidence_score") or 0.9)
            prediction_source = "CONFIDENT_MERCHANT"
            prediction_status = "OK"
            merchant_name     = matched["merchant_name"]
            merchant_id_out   = matched["merchant_id"]
        else:
            primary_cat_id    = None
            confidence        = 0.0
            prediction_source = "UNCLASSIFIED"
            prediction_status = "UNCLASSIFIED"
            merchant_name     = merchant_candidate or ""
            merchant_id_out   = ""
            _add_to_learning_pool(merchant_candidate, user_id)

            # Generate behavioral suggestions for user to confirm later
            try:
                behavior_result = generate_suggestions(
                    user_id=user_id,
                    transaction={
                        "transaction_id": txn_id,
                        "amount":         parsing_meta.get("amount", 0.0),
                        "timestamp":      txn.get("transaction_date") or txn.get("created_at"),
                    },
                )
            except Exception as e:
                print(f"Warning: behavior engine error for {txn_id}: {e}")
                behavior_result = None

        supabase.table("transactions").update({
            "normalized_text":  normalized_text or raw_text,
            "merchant_name":    merchant_name or txn.get("merchant_name"),
            "merchant_id":      merchant_id_out or txn.get("merchant_id"),
            "parsing_metadata": parsing_meta,
        }).eq("id", txn_id).execute()

        cat_row = {
            "transaction_id":      txn_id,
            "user_id":             user_id,
            "primary_category_id": primary_cat_id,
            "primary_confidence":  confidence,
            "prediction_source":   prediction_source,
            "prediction_status":   prediction_status,
            "rule_metadata": {
                "merchant_candidate": merchant_candidate,
                "merchant_name":      merchant_name,
                "merchant_id":        merchant_id_out,
                "matched_from":       "confident_merchants" if matched else "none",
            },
        }
        if not matched and behavior_result:
            cat_row["behavioral_suggestions"] = behavior_result
        supabase.table("transaction_categorizations").upsert(
            cat_row, on_conflict="transaction_id"
        ).execute()

        supabase.table("transactions").update({"is_processed": True}).eq("id", txn_id).execute()

        if matched:
            print(f"[OK] {txn_id} -> {prediction_source} | {merchant_name}")
        else:
            n_suggestions = len((behavior_result or {}).get("suggestions", []))
            print(f"[??] {txn_id} -> UNCLASSIFIED | {merchant_name or 'UNKNOWN'} | {n_suggestions} suggestion(s)")

    print("Categorization batch complete.")


if __name__ == "__main__":
    run_auto_categorization()
