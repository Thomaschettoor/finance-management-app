"""
Promotion Service
-----------------
Checks global_merchant_learning for merchants that meet the threshold:
  total_reports >= 40, total_unique_users >= 20, category_confidence >= 0.85
Promotes them to confident_merchants (source=crowd_promoted) and deletes from pool.
"""
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

PROMOTION_MIN_REPORTS      = 40
PROMOTION_MIN_UNIQUE_USERS = 20
PROMOTION_MIN_CONFIDENCE   = 0.85


def run_promotion():
    candidates = (
        supabase.table("global_merchant_learning")
        .select("*")
        .gte("total_reports",       PROMOTION_MIN_REPORTS)
        .gte("total_unique_users",  PROMOTION_MIN_UNIQUE_USERS)
        .gte("category_confidence", PROMOTION_MIN_CONFIDENCE)
        .execute().data or []
    )
    print(f"[Promotion] {len(candidates)} candidate(s)")

    for m in candidates:
        mid      = m["merchant_id"]
        mname    = m.get("merchant_name") or mid
        cat_id   = m.get("leading_category_id")
        cat_conf = float(m.get("category_confidence") or 0)

        if not cat_id:
            print(f"  SKIP {mid} - no leading_category_id")
            continue
        try:
            supabase.table("confident_merchants").upsert({
                "merchant_id":         mid,
                "merchant_name":       mname,
                "aliases":             "[]",
                "primary_category_id": cat_id,
                "confidence_score":    cat_conf,
                "source":              "crowd_promoted",
            }, on_conflict="merchant_id").execute()
            supabase.table("global_merchant_learning").delete().eq("merchant_id", mid).execute()
            print(f"  PROMOTED {mname} ({mid}) -> {cat_id} @ {cat_conf:.2f}")
        except Exception as e:
            print(f"  ERROR {mid}: {e}")


if __name__ == "__main__":
    run_promotion()
