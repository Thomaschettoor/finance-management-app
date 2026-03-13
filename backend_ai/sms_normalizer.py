import re
import re
from typing import Dict, Any, Tuple


AMOUNT_PATTERNS = [
    r"(?:rs\.?|inr)\s*([0-9,]+(?:\.[0-9]{1,2})?)",
    r"([0-9,]+(?:\.[0-9]{1,2})?)\s*(?:rs\.?|inr)",
]

PAYMENT_METHOD_KEYWORDS = {
    "upi": ["upi", "vpa", "@ok", "@ybl", "@oksbi", "@ibl", "@paytm"],
    "imps": ["imps"],
    "neft": ["neft"],
    "card": ["card", "visa", "mastercard", "rupay"],
}

DEBIT_KEYWORDS = ["debited", "debit", "sent", "paid", "withdrawn", "spent"]
CREDIT_KEYWORDS = ["credited", "credit", "received", "refund"]


def _extract_amount(text: str) -> Tuple[float, str]:
    t = text.lower()
    for pat in AMOUNT_PATTERNS:
        m = re.search(pat, t)
        if m:
            try:
                # Remove commas from amount string before converting to float
                amount_str = m.group(1).replace(',', '')
                return float(amount_str), "INR"
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
    # Heuristic 0: merchant may appear at the very start before the currency word
    # e.g. "PVR INR 599 debited...".  We explicitly avoid matching the word INR/RS
    # itself so that "INR 599 at PVR" doesn't return INR.
    m0 = re.match(
        r"^([A-Za-z]+?)(?:\s*(?:rs\.?|inr|₹))",
        text,
        flags=re.IGNORECASE,
    )
    if m0:
        cand = m0.group(1).strip()
        if cand.lower() not in ("inr", "rs"):
            return cand

    # Heuristic 1: capture merchant names after keywords like 'to', 'at', 'via', 'on', 'for'
    # Improved to handle concatenated text like "iKEAINR" and limit capture length
    # Use findall to get all matches, then filter out banking terms
    t = text
    matches = re.findall(r"\b(?:to|at|via|on|for)\s+([A-Za-z0-9@.\-]+)", t, flags=re.IGNORECASE)
    
    # Filter out common banking/card terms that shouldn't be merchants
    banking_terms = {"your", "my", "a", "the", "this", "card", "account", "bank", "hdfc", "sbi", "icici", "axis", "ending"}
    
    for merchant_candidate in matches:
        merchant_lower = merchant_candidate.lower().strip()
        
        # Skip banking terms
        if merchant_lower in banking_terms:
            continue
            
        # Handle concatenated currency words like "iKEAINR" - extract just the merchant part
        currency_pattern = re.search(r"^(.+?)(?:inr|rs|₹)(?:[0-9]|$)", merchant_candidate, flags=re.IGNORECASE)
        if currency_pattern:
            clean_merchant = currency_pattern.group(1).strip()
            if len(clean_merchant) >= 2 and clean_merchant.lower() not in ("inr", "rs"):
                return clean_merchant
        
        # If no currency suffix found, return the first word if it's valid
        first_word = merchant_candidate.split()[0]
        if len(first_word) >= 2 and first_word.lower() not in ("inr", "rs"):
            return first_word

    # Heuristic 2: Look for merchant names within concatenated currency patterns
    # e.g., "iKEAINR" -> extract "iKEA"
    currency_concat = re.search(r"\b([A-Za-z]{2,}?)(?:inr|rs)(?:[0-9]|\s|$)", text, flags=re.IGNORECASE)
    if currency_concat:
        candidate = currency_concat.group(1).strip()
        if candidate.lower() not in ("inr", "rs", "from", "card", "hdfc", "sbi", "icici", "axis"):
            return candidate

    # fallback: look for capitalized word sequences, excluding common banking terms
    caps = re.findall(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*)\b", text)
    if caps:
        # Filter out common banking/financial terms
        excluded_terms = {"HDFC", "SBI", "ICICI", "AXIS", "INR", "UPI", "NEFT", "IMPS"}
        filtered_caps = [cap for cap in caps if cap.upper() not in excluded_terms]
        return max(filtered_caps, key=len) if filtered_caps else ""
    
    return ""


def normalize_text(raw_text: str) -> Tuple[str, Dict[str, Any]]:
    if not raw_text:
        return "", {}

    # Preserve original for metadata analysis
    original = raw_text.strip()

    # Basic cleanup and lowercase copy for parsing keyword detection
    lower = re.sub(r"[^A-Za-z0-9@\s\.]", " ", original).lower()
    lower = re.sub(r"\s+", " ", lower).strip()

    # Extract amount from original to preserve commas (e.g., "1,299.00")
    amount, currency = _extract_amount(original)
    txn_type = _detect_transaction_type(lower)
    payment_method = _detect_payment_method(lower)
    merchant_candidate = _candidate_merchant_tokens(original)

    # Extract VPA (UPI handle) if present (e.g., name@bank)
    vpa_match = re.search(r"([a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+)", original)
    vpa = vpa_match.group(1) if vpa_match else ""

    # Remove common boilerplate marketing lines and URLs from normalized text
    cleaned = re.sub(r"https?://\S+", " ", original, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:know more|download|click here|visit|visit us|offer|congrats|hurry|win|redeem now)\b.*", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Canonical normalized text for ML: start from cleaned text, remove long txn ids
    normalized = re.sub(r"\b[0-9A-Z]{8,}\b", " ", cleaned)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    metadata = {
        "amount": amount,
        "currency": currency,
        "transaction_type": txn_type,
        "payment_method": payment_method,
        "merchant_candidate": merchant_candidate,
        "vpa": vpa,
        "original": original,
    }

    return normalized, metadata
