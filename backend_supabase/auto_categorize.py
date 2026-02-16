from urllib import response
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
# Import AI engine
from backend_ai.categorization_engine import predict_transaction

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

        # ✅ AI prediction
        result = predict_transaction(raw_text)

        # ✅ Insert categorization result
        supabase.table("transaction_categorizations").upsert({
            "transaction_id": txn_id,
            "user_id": user_id,
            "primary_category_id": CATEGORY_MAP[result["primary"]],
            "primary_confidence": result["primary_confidence"],
            "suggestion_2_category_id": CATEGORY_MAP[result["suggestion_2"]],
            "suggestion_2_confidence": result["suggestion_2_confidence"],
            "suggestion_3_category_id": CATEGORY_MAP[result["suggestion_3"]],
            "suggestion_3_confidence": result["suggestion_3_confidence"],
            "prediction_source": "MODEL",
            "model_version": "v1"
        },on_conflict="transaction_id").execute()

        # ✅ VERY IMPORTANT — mark transaction processed
        supabase.table("transactions").update({
            "is_processed": True
        }).eq("id", txn_id).execute()

        print(f"✅ Categorized transaction {txn_id}")

    print("🎯 Categorization complete.")


if __name__ == "__main__":
    run_auto_categorization()