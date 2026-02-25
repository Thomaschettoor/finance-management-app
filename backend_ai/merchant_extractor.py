from typing import Dict, Any, List, Tuple
from difflib import SequenceMatcher
import re


# Minimum score required to report a merchant match (prevents false defaults)
MIN_MATCH_SCORE = 0.65

ALIASES = {
    # Food & Dining
    "swiggy": ["swiggy", "swiggy.in"],
    "zomato": ["zomato", "zomato.com", "zomatolimited", "zomatomedia"],
    "dominos": ["dominos", "domino", "dominos pizza"],
    "mcdonalds": ["mcdonalds", "mcd", "mcdonald"],
    # Shopping
    "amazon": ["amazon", "amazonpay", "amazon.in"],
    "flipkart": ["flipkart", "fkrt"],
    "myntra": ["myntra"],
    "bigbasket": ["bigbasket", "big basket"],
    "dmart": ["dmart", "dmartindia", "d mart"],
    "reliance fresh": ["reliance fresh", "reliancefresh"],
    # Entertainment
    "netflix": ["netflix"],
    "bookmyshow": ["bookmyshow", "bms", "book my show"],
    "spotify": ["spotify"],
    "hotstar": ["hotstar", "disney hotstar", "disneyplus"],
    "primevideo": ["prime video", "primevideo", "amazon prime"],
    # Transport
    "uber": ["uber", "uberindia"],
    "ola": ["ola", "ola cabs"],
    "rapido": ["rapido"],
    "indriver": ["indriver", "indrive"],
    # Utilities
    "jio": ["jio", "reliance jio"],
    "airtel": ["airtel"],
    "vi": ["vi", "vodafone idea", "vodafoneidea"],
    "electricity board": ["electricity board", "ebill", "electric board", "bescom", "mseb", "pspcl", "bses", "tneb"],
    "water supply": ["water supply", "water board", "bwssb"],
    # Wallets / Payments
    "paytm": ["paytm"],
    # Gambling
    "dream11": ["dream11"],
    "rummycircle": ["rummycircle", "rummy circle", "rummy"],
    "pokerstars": ["pokerstars", "poker stars"],
    "mpl": ["mpl", "mobile premier league", "mplapp", "mplpro"],
    # Health
    "medplus": ["medplus", "med plus"],
    "hospital": ["hospital", "clinic", "apollo", "fortis", "manipal"],
}


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def extract_merchant(candidate: str, merchant_db: List[Dict[str, Any]] | None = None) -> Tuple[str, str, float, Dict[str, Any]]:
    """
    Extract merchant using built-in aliases plus optional `merchant_db` records
    (from `global_merchant_intelligence`). Returns (merchant_name, merchant_id, score, meta).
    """
    if not candidate:
        return "", "", 0.0, {"reason": "no_candidate"}

    # Clean and tokenize candidate to remove common noise tokens like 'upi', 'txn', 'ref'
    candidate_clean = re.sub(r"\b(upi|txn|tx|ref|id|via|paid|debited|credited)\b", " ", candidate, flags=re.IGNORECASE)
    tokens = re.findall(r"[A-Za-z0-9]+", candidate_clean.lower())

    best_name = ""
    best_id = ""
    best_score = 0.0
    matched_alias = ""
    matched_record: Dict[str, Any] | None = None

    # First match against merchant_db (if provided) for authoritative mappings
    if merchant_db:
        for rec in merchant_db:
            # rec may include merchant_name and merchant_id
            rec_name = (rec.get("merchant_name") or "").lower()
            rec_id = str(rec.get("merchant_id") or "").lower()
            # compare full candidate and tokens
            score_full = _similar(candidate_clean, rec_name) if rec_name else 0.0
            score_id = _similar(candidate_clean, rec_id) if rec_id else 0.0
            score_tokens = max((_similar(tok, rec_name) for tok in tokens), default=0.0) if rec_name else 0.0
            score = max(score_full, score_id, score_tokens)
            if score > best_score:
                best_score = score
                best_name = rec.get("merchant_name") or rec_id
                best_id = rec.get("merchant_id") or rec_id
                matched_alias = rec_name
                matched_record = rec

    # Fallback to built-in ALIASES
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            score_full = _similar(candidate_clean, alias)
            score_tokens = max((_similar(tok, alias) for tok in tokens), default=0.0)
            score = max(score_full, score_tokens)
            if score > best_score:
                best_score = score
                best_name = canonical.capitalize()
                best_id = canonical
                matched_alias = alias
                matched_record = None

    # If best score is below threshold, treat as unknown (prevents false defaults)
    if best_score < MIN_MATCH_SCORE:
        best_name = ""
        best_id = ""
        matched_alias = ""
        matched_record = None

    meta = {
        "candidate": candidate,
        "clean": candidate_clean,
        "matched_alias": matched_alias,
        "tokens": tokens,
        "matched_record": matched_record,
    }
    return best_name, best_id, float(best_score), meta
