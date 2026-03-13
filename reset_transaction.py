from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

txn_id = 'c31eef46-93f4-4be1-89c2-aa3cad96d3d7'

# Reset the transaction for reprocessing
print(f"Resetting transaction {txn_id}...")
sb.table('transactions').update({'is_processed': False}).eq('id', txn_id).execute()

# Delete old categorization
print("Deleting old categorization...")
sb.table('transaction_categorizations').delete().eq('transaction_id', txn_id).execute()

print("Transaction reset complete. Ready for reprocessing.")
