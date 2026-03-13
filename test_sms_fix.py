import sys
sys.path.insert(0, '/Users/thomastomy/finance-management-app-1')

from backend_ai.sms_normalizer import normalize_text

sms_text = '"Rs.1,299.00 spent on your HDFC Bank Credit Card ending 4432 at SWIGGY on 12-03-26"'

normalized, metadata = normalize_text(sms_text)

print("=== SMS PARSING TEST ===")
print(f"Raw SMS: {sms_text}")
print(f"\nNormalized: {normalized}")
print(f"\n=== METADATA ===")
print(f"Amount: {metadata.get('amount')}")
print(f"Currency: {metadata.get('currency')}")
print(f"Transaction Type: {metadata.get('transaction_type')}")
print(f"Payment Method: {metadata.get('payment_method')}")
print(f"Merchant Candidate: {metadata.get('merchant_candidate')}")
print(f"VPA: {metadata.get('vpa')}")
