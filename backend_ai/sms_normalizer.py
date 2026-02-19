import re
from typing import Dict, Any, Tuple


AMOUNT_PATTERNS = [
    r"(?:rs\.?|inr)\s*([0-9]+(?:\.[0-9]{1,2})?)",
    r"([0-9]+(?:\.[0-9]{1,2})?)\s*(?:rs\.?|inr)",
]

PAYMENT_METHOD_KEYWORDS = {
    "upi": ["upi", "vpa", "@ok", "@ybl", "@oksbi", "@ibl", "@paytm"],
    "imps": ["imps"],
    "neft": ["neft"],
    "card": ["card", "visa", "mastercard", "rupay"],
}

DEBIT_KEYWORDS = ["debited", "debit", "sent", "paid", "withdrawn"]
CREDIT_KEYWORDS = ["credited", "credit", "received", "refund"]


def _extract_amount(text: str) -> Tuple[float, str]:
    t = text.lower()
    for pat in AMOUNT_PATTERNS:
        m = re.search(pat, t)
        if m:
            try:
                return float(m.group(1)), "INR"
            except Exception:
                continue
    return 0.0, "INR"


def _detect_transaction_type(text: str) -> str:
    t = text.lower()
    if any(k in t for k in DEBIT_KEYWORDS):
        return "DEBIT"
    if any(k in t for k in CREDIT_KEYWORDS):
        return "CREDIT"
    return "DEBIT"  # default assumption for expenses


def _detect_payment_method(text: str) -> str:
    t = text.lower()
    for method, kws in PAYMENT_METHOD_KEYWORDS.items():
        if any(k in t for k in kws):
            return method.upper()
    return "UPI"


def _candidate_merchant_tokens(text: str) -> str:
    # Heuristic: capture a short phrase (up to 5 tokens) after keywords like
    # 'to', 'at', 'via', 'on', 'for' — this catches multi-word merchants like
    # 'UPI SWIGGY' or 'PAYTM SHOP'
    t = text
    m = re.search(r"\b(?:to|at|via|on|for)\s+([A-Za-z0-9@.\-]+(?:\s+[A-Za-z0-9@.\-]+){0,4})",
                  t, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # fallback: look for capitalized word sequences and return the longest
    caps = re.findall(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*)\b", text)
    return max(caps, key=len) if caps else ""


def normalize_text(raw_text: str) -> Tuple[str, Dict[str, Any]]:
    if not raw_text:
        return "", {}

    # Preserve original for metadata analysis
    original = raw_text.strip()

    # Basic cleanup and lowercase copy for parsing
    lower = re.sub(r"[^A-Za-z0-9@\s\.]", " ", original).lower()
    lower = re.sub(r"\s+", " ", lower).strip()

    amount, currency = _extract_amount(lower)
    txn_type = _detect_transaction_type(lower)
    payment_method = _detect_payment_method(lower)
    merchant_candidate = _candidate_merchant_tokens(original)

    # Canonical normalized text for ML: remove reference numbers and long numeric ids
    normalized = re.sub(r"\b[0-9A-Z]{8,}\b", " ", original)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    metadata = {
        "amount": amount,
        "currency": currency,
        "transaction_type": txn_type,
        "payment_method": payment_method,
        "merchant_candidate": merchant_candidate,
        "original": original,
    }

    return normalized, metadata
