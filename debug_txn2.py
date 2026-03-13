from supabase import create_client
import os
from dotenv import load_dotenv
import json
import sys

load_dotenv()
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

if len(sys.argv) > 1:
    txn_id = sys.argv[1]
else:
    txn_id = '306d1072-dc0e-40de-a44e-276b82fb5240'

print(f"Looking up transaction {txn_id}")

txn = sb.table('transactions').select('*').eq('id', txn_id).execute()
if txn.data:
    t = txn.data[0]
    print('Transaction:', json.dumps(t, indent=2, default=str))
    print('is_processed', t.get('is_processed'))
    print('normalized', t.get('normalized_text'))
    print('raw', t.get('raw_text'))
    print('parsing', json.dumps(t.get('parsing_metadata'), indent=2))
else:
    print('transaction not found')

cat = sb.table('transaction_categorizations').select('*').eq('transaction_id', txn_id).execute()
print('categorization', cat.data)
