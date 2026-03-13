from supabase import create_client
import os
from dotenv import load_dotenv
import json

load_dotenv()
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

txn_id = 'c31eef46-93f4-4be1-89c2-aa3cad96d3d7'

# Get transaction
txn = sb.table('transactions').select('*').eq('id', txn_id).execute()
if txn.data:
    print('=== TRANSACTION ===')
    t = txn.data[0]
    print(f'ID: {t["id"]}')
    print(f'User: {t["user_id"]}')
    print(f'Amount: {t.get("amount")}')
    print(f'Merchant Name: {t.get("merchant_name")}')
    print(f'Merchant ID: {t.get("merchant_id")}')
    print(f'Raw Text: {t.get("raw_text")}')
    print(f'Normalized: {t.get("normalized_text")}')
    print(f'Is Processed: {t.get("is_processed")}')
    print(f'Parsing Metadata: {json.dumps(t.get("parsing_metadata"), indent=2)}')
    print()
    
    # Get categorization
    cat = sb.table('transaction_categorizations').select('*').eq('transaction_id', txn_id).execute()
    if cat.data:
        print('=== CATEGORIZATION ===')
        c = cat.data[0]
        print(f'Primary Category ID: {c.get("primary_category_id")}')
        print(f'Confidence: {c.get("primary_confidence")}')
        print(f'Source: {c.get("prediction_source")}')
        print(f'Status: {c.get("prediction_status")}')
        print(f'Rule Metadata: {json.dumps(c.get("rule_metadata"), indent=2)}')
        if c.get('behavioral_suggestions'):
            print(f'Behavioral Suggestions: {json.dumps(c.get("behavioral_suggestions"), indent=2)}')
    else:
        print('=== NO CATEGORIZATION FOUND ===')
else:
    print('Transaction not found')
