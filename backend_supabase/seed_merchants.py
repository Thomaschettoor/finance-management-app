"""Seed confident_merchants table - source of truth for transaction categorization."""
import json
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MERCHANT_SEED = [
    # Food & Dining
    {"merchant_id": "zomato",           "merchant_name": "Zomato",          "aliases": ["zomato", "zomatomedia", "zomato.com"],                                          "primary_category_id": "31dd2d93-25f4-43c6-9833-6816d8a1bfce", "confidence_score": 0.98},
    {"merchant_id": "swiggy",           "merchant_name": "Swiggy",          "aliases": ["swiggy", "swiggy.in"],                                                          "primary_category_id": "31dd2d93-25f4-43c6-9833-6816d8a1bfce", "confidence_score": 0.98},
    {"merchant_id": "dominos",          "merchant_name": "Dominos",         "aliases": ["dominos", "domino", "dominos pizza"],                                           "primary_category_id": "31dd2d93-25f4-43c6-9833-6816d8a1bfce", "confidence_score": 0.96},
    {"merchant_id": "mcdonalds",        "merchant_name": "McDonalds",       "aliases": ["mcdonalds", "mcd", "mcdonald"],                                                 "primary_category_id": "31dd2d93-25f4-43c6-9833-6816d8a1bfce", "confidence_score": 0.95},
    # Shopping
    {"merchant_id": "amazon",           "merchant_name": "Amazon",          "aliases": ["amazon", "amazon.in", "amazonpay"],                                             "primary_category_id": "b2104a33-0a09-44b1-9026-195e01c73ddc", "confidence_score": 0.95},
    {"merchant_id": "flipkart",         "merchant_name": "Flipkart",        "aliases": ["flipkart", "fkrt"],                                                             "primary_category_id": "b2104a33-0a09-44b1-9026-195e01c73ddc", "confidence_score": 0.95},
    {"merchant_id": "myntra",           "merchant_name": "Myntra",          "aliases": ["myntra"],                                                                        "primary_category_id": "b2104a33-0a09-44b1-9026-195e01c73ddc", "confidence_score": 0.95},
    {"merchant_id": "dmart",            "merchant_name": "DMart",           "aliases": ["dmart", "dmartindia", "d mart"],                                                "primary_category_id": "b2104a33-0a09-44b1-9026-195e01c73ddc", "confidence_score": 0.94},
    {"merchant_id": "bigbasket",        "merchant_name": "BigBasket",       "aliases": ["bigbasket", "big basket"],                                                      "primary_category_id": "b2104a33-0a09-44b1-9026-195e01c73ddc", "confidence_score": 0.93},
    {"merchant_id": "reliance_fresh",   "merchant_name": "Reliance Fresh",  "aliases": ["reliance fresh", "reliancefresh"],                                              "primary_category_id": "b2104a33-0a09-44b1-9026-195e01c73ddc", "confidence_score": 0.92},
    # Entertainment
    {"merchant_id": "netflix",          "merchant_name": "Netflix",         "aliases": ["netflix"],                                                                       "primary_category_id": "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d", "confidence_score": 0.98},
    {"merchant_id": "bookmyshow",       "merchant_name": "BookMyShow",      "aliases": ["bookmyshow", "bms", "book my show"],                                            "primary_category_id": "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d", "confidence_score": 0.97},
    {"merchant_id": "spotify",          "merchant_name": "Spotify",         "aliases": ["spotify"],                                                                       "primary_category_id": "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d", "confidence_score": 0.97},
    {"merchant_id": "hotstar",          "merchant_name": "Hotstar",         "aliases": ["hotstar", "disney hotstar", "disneyplus"],                                      "primary_category_id": "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d", "confidence_score": 0.97},
    {"merchant_id": "primevideo",       "merchant_name": "Prime Video",     "aliases": ["prime video", "primevideo", "amazon prime"],                                    "primary_category_id": "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d", "confidence_score": 0.96},
    {"merchant_id": "dream11",          "merchant_name": "Dream11",         "aliases": ["dream11"],                                                                       "primary_category_id": "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d", "confidence_score": 0.95},
    {"merchant_id": "pokerstars",       "merchant_name": "PokerStars",      "aliases": ["pokerstars", "poker stars"],                                                     "primary_category_id": "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d", "confidence_score": 0.95},
    {"merchant_id": "mpl",              "merchant_name": "MPL",             "aliases": ["mpl", "mobile premier league"],                                                  "primary_category_id": "bcf0aaae-f06f-4bb7-b9e5-2db48fa59d0d", "confidence_score": 0.95},
    # Transportation
    {"merchant_id": "uber",             "merchant_name": "Uber",            "aliases": ["uber", "uberindia"],                                                             "primary_category_id": "1da57196-d4fb-4785-96d1-3fbe7cc34e58", "confidence_score": 0.97},
    {"merchant_id": "ola",              "merchant_name": "Ola",             "aliases": ["ola", "ola cabs"],                                                              "primary_category_id": "1da57196-d4fb-4785-96d1-3fbe7cc34e58", "confidence_score": 0.97},
    {"merchant_id": "rapido",           "merchant_name": "Rapido",          "aliases": ["rapido"],                                                                        "primary_category_id": "1da57196-d4fb-4785-96d1-3fbe7cc34e58", "confidence_score": 0.96},
    # Utilities & Bills
    {"merchant_id": "jio",              "merchant_name": "Jio",             "aliases": ["jio", "reliance jio"],                                                          "primary_category_id": "429fcded-f706-4576-8858-a4421f57a8b1", "confidence_score": 0.95},
    {"merchant_id": "airtel",           "merchant_name": "Airtel",          "aliases": ["airtel"],                                                                        "primary_category_id": "429fcded-f706-4576-8858-a4421f57a8b1", "confidence_score": 0.95},
    {"merchant_id": "vi",               "merchant_name": "Vi",              "aliases": ["vi", "vodafone idea", "vodafoneidea"],                                          "primary_category_id": "429fcded-f706-4576-8858-a4421f57a8b1", "confidence_score": 0.94},
    {"merchant_id": "electricity_board","merchant_name": "Electricity Board","aliases": ["electricity board", "electric board", "ebill", "bescom", "mseb", "pspcl", "bses", "tneb"], "primary_category_id": "429fcded-f706-4576-8858-a4421f57a8b1", "confidence_score": 0.97},
    {"merchant_id": "water_supply",     "merchant_name": "Water Supply",    "aliases": ["water supply", "water board", "bwssb"],                                         "primary_category_id": "429fcded-f706-4576-8858-a4421f57a8b1", "confidence_score": 0.97},
    # Transfer & Wallet
    {"merchant_id": "paytm",            "merchant_name": "Paytm",           "aliases": ["paytm"],                                                                         "primary_category_id": "fecd0afa-5522-416e-b8b8-c08bbb3fe993", "confidence_score": 0.90},
    {"merchant_id": "company_payroll",  "merchant_name": "Company Payroll", "aliases": ["salary", "payroll", "company payroll", "payslip"],                              "primary_category_id": "fecd0afa-5522-416e-b8b8-c08bbb3fe993", "confidence_score": 0.92},
    # Others
    {"merchant_id": "house_owner",      "merchant_name": "House Owner",     "aliases": ["house owner", "rent", "house rent"],                                            "primary_category_id": "3880903c-bc06-44f1-9eed-da04124feb70", "confidence_score": 0.88},
    # Health & Fitness
    {"merchant_id": "medplus",          "merchant_name": "MedPlus",         "aliases": ["medplus", "med plus"],                                                           "primary_category_id": "4a71ecfa-554a-49f8-8daf-004a99dcda21", "confidence_score": 0.95},
    {"merchant_id": "hospital",         "merchant_name": "Hospital",        "aliases": ["hospital", "clinic", "apollo", "fortis", "manipal", "max"],                    "primary_category_id": "4a71ecfa-554a-49f8-8daf-004a99dcda21", "confidence_score": 0.92},
]

def seed():
    for rec in MERCHANT_SEED:
        try:
            supabase.table("confident_merchants").upsert({
                "merchant_id":         rec["merchant_id"],
                "merchant_name":       rec["merchant_name"],
                "aliases":             json.dumps(rec["aliases"]),
                "primary_category_id": rec["primary_category_id"],
                "confidence_score":    rec["confidence_score"],
                "source":              "seeded",
            }, on_conflict="merchant_id").execute()
            print("  OK  " + rec["merchant_id"])
        except Exception as e:
            print("  ERR " + rec["merchant_id"] + ": " + str(e))

if __name__ == "__main__":
    seed()
