from urllib import response
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
# Feature flag: enable/disable merchant-based rule boosting (set to 'false' to disable)
RULE_BOOSTING_ENABLED = os.getenv("RULE_BOOSTING_ENABLED", "true").lower() in ("1", "true", "yes")
# Import AI engine
from backend_ai.categorization_engine import predict_transaction
from backend_ai.confidence_calibrator import load_calibrator, calibrate_prob
from backend_ai.sms_normalizer import normalize_text
from backend_ai.merchant_extractor import extract_merchant

BATCH_SIZE = 50
# -------------------------
# SUPABASE CONFIG
# -------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# -------------------------
# CATEGORY MAP
# -------------------------
CATEGORY_MAP = {
    "Food & Dining": "31dd2d93-25f4-43c6-9833-6816d8a1bfce",
    "Shopping": "b2104a33-0a09-44b1-9026-195e01c73ddc",
    "Transportation": "1da57196-d4fb-4785-96d1-3fbe7cc34e58",
    "Utilities & Bills": "429fcded-f706-4576-8858-a4421f57a8b1",
    "Entertainment": "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d",
    "Health & Fitness": "4a71ecfa-554a-49f8-8daf-004a99dcda21",
    "Transfer & Wallet": "fecd0afa-5522-416e-b8b8-c08bbb3fe993",
    "Others": "3880903c-bc06-44f1-9eed-da04124feb70",
    "Education": "00bbd2d8-7f0b-4f01-b481-3d81aae5c813",
    "Gifts & Donations": "18e662e7-5ab7-4482-94e3-777d81a20c68",
    "Subscriptions": "18f7fb6a-8fe8-46fa-8765-8680064b8655",
    "Financial Services": "2e0c0c8b-b2f1-41fe-bda1-8e8e984ea13e",
    "Travel & Lodging": "308f79a8-204d-4cad-ac56-ed0f191e3937",
    "Personal Care": "8af77e68-fb27-4a54-9e0a-cdaa779dbbae"
}


def run_auto_categorization():

    # ✅ Fetch ONLY unprocessed transactions
    txn_response = supabase.table("transactions") \
        .select("*") \
        .eq("is_processed", False) \
        .limit(BATCH_SIZE) \
        .execute()

    # ✅ safe extraction
    transactions = txn_response.data or []

    print(f"Found {len(transactions)} transactions to categorize")

    for txn in transactions:

        raw_text = txn.get("raw_text")

        # ✅ Skip empty SMS
        if not raw_text:
            continue

        txn_id = txn["id"]
        user_id = txn["user_id"]

        # 🔎 Phase B: Normalize SMS and extract merchant
        normalized_text, parsing_meta = normalize_text(raw_text)

        # Fetch merchant intelligence (can be empty) to use for authoritative matches
        merchant_db_resp = supabase.table("global_merchant_intelligence").select("*").execute()
        merchant_db = merchant_db_resp.data or []

        merchant_name, merchant_id, merchant_score, merchant_meta = extract_merchant(
            parsing_meta.get("merchant_candidate", ""), merchant_db=merchant_db
        )

        # Update transaction with normalized fields (non-destructive)
        supabase.table("transactions").update({
            "normalized_text": normalized_text or raw_text,
            "merchant_name": merchant_name or txn.get("merchant_name"),
            "merchant_id": merchant_id or txn.get("merchant_id"),
            "merchant_match_confidence": merchant_score,
            "parsing_metadata": {**parsing_meta, **{"merchant": merchant_meta}},
        }).eq("id", txn_id).execute()

        # ✅ AI prediction
        # Use normalized text for better ML signal
        result = predict_transaction(normalized_text or raw_text)

        # Apply calibration to model confidence if a calibrator exists
        try:
            model_conf = float(result.get("primary_confidence") or 0)
            calibrated = calibrate_prob(model_conf)
            result["primary_confidence_calibrated"] = calibrated
        except Exception:
            result["primary_confidence_calibrated"] = result.get("primary_confidence")

        # ------------------
        # Rule-based boosting (simple hybrid)
        # If merchant matched with high confidence and the merchant DB records
        # include a `primary_category_id`, prefer that category (or hybrid)
        # ------------------
        applied_rule = None
        prediction_source = "MODEL"
        boosted_primary_id = None
        boosted_primary_conf = None

        if RULE_BOOSTING_ENABLED and merchant_score >= 0.8 and merchant_meta.get("matched_record"):
            rec = merchant_meta.get("matched_record")
            primary_cat = rec.get("primary_category_id")
            cat_conf = float(rec.get("category_confidence") or 0)
            if primary_cat:
                # Choose higher confidence between calibrated model and merchant intelligence
                model_conf_used = float(result.get("primary_confidence_calibrated") or result.get("primary_confidence") or 0)
                boosted_primary_conf = max(model_conf_used, cat_conf)
                boosted_primary_id = primary_cat
                prediction_source = "HYBRID_RULE"
                applied_rule = {
                    "reason": "merchant_primary_category",
                    "merchant_id": rec.get("merchant_id"),
                    "merchant_name": rec.get("merchant_name"),
                    "merchant_category_confidence": cat_conf,
                }

        # ✅ Insert categorization result
        # Prepare final categorization payload, possibly overridden by rule
        primary_cat_id = CATEGORY_MAP.get(result["primary"])
        primary_conf = float(result["primary_confidence"])

        if boosted_primary_id:
            primary_cat_id = boosted_primary_id
            primary_conf = float(boosted_primary_conf)

        payload = {
            "transaction_id": txn_id,
            "user_id": user_id,
            "primary_category_id": primary_cat_id,
            "primary_confidence": primary_conf,
            "suggestion_2_category_id": CATEGORY_MAP.get(result["suggestion_2"]),
            "suggestion_2_confidence": result["suggestion_2_confidence"],
            "suggestion_3_category_id": CATEGORY_MAP.get(result["suggestion_3"]),
            "suggestion_3_confidence": result["suggestion_3_confidence"],
            "prediction_source": prediction_source,
            "model_version": "v1",
            "prediction_status": result["status"],
            "rule_metadata": {
                "merchant_name": merchant_name,
                "merchant_id": merchant_id,
                "merchant_match_confidence": merchant_score,
            },
        }

        if applied_rule:
            payload["rule_metadata"]["applied_rule"] = applied_rule

        supabase.table("transaction_categorizations").upsert(payload, on_conflict="transaction_id").execute()

        # Audit HYBRID_RULE overrides when applied
        if prediction_source == "HYBRID_RULE" and applied_rule:
            try:
                supabase.table("hybrid_rule_audit").insert({
                    "transaction_id": txn_id,
                    "user_id": user_id,
                    "merchant_id": applied_rule.get("merchant_id"),
                    "merchant_name": applied_rule.get("merchant_name"),
                    "rule": applied_rule,
                    "model_confidence": float(result.get("primary_confidence") or 0),
                    "rule_confidence": float(applied_rule.get("merchant_category_confidence") or 0),
                    "resulting_category_id": primary_cat_id,
                    "prediction_source": prediction_source,
                }).execute()
            except Exception as e:
                print("⚠️ Failed to write hybrid_rule_audit:", e)

        # ✅ VERY IMPORTANT — mark transaction processed
        supabase.table("transactions").update({
            "is_processed": True
        }).eq("id", txn_id).execute()

        print(f"✅ Categorized transaction {txn_id}")

    print("🎯 Categorization complete.")


if __name__ == "__main__":
    run_auto_categorization()