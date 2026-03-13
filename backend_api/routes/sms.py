"""
SMS Ingestion routes
--------------------
POST /api/v1/sms/ingest  — process incoming SMS and create transaction
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
import os

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from supabase import create_client
from dotenv import load_dotenv

from backend_api.auth import get_current_user
from backend_ai.sms_normalizer import normalize_text
from backend_ai.merchant_extractor import extract_merchant

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

router = APIRouter(prefix="/sms", tags=["SMS"])


# ── Models ────────────────────────────────────────────────────────────────────

class SMSIngestRequest(BaseModel):
    sms_text: str
    sender: str = ""
    timestamp: Optional[str] = None


class SMSIngestResponse(BaseModel):
    transaction_id: str
    status: str
    merchant_name: str = ""
    amount: float = 0.0
    transaction_type: str = ""
    message: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=SMSIngestResponse)
async def ingest_sms_transaction(
    request: SMSIngestRequest,
    user_id: str = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
):
    """
    Process incoming SMS text and create a transaction record.
    
    The SMS is parsed to extract merchant, amount, and transaction type.
    A new transaction is created and queued for categorization.
    """
    try:
        # Step 1: Parse the SMS text
        normalized_text, parsing_meta = normalize_text(request.sms_text)
        
        if not parsing_meta:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to parse SMS text"
            )
        
        # Step 2: Extract merchant information
        merchant_candidate = parsing_meta.get("merchant_candidate", "")
        
        # Get merchant database for better extraction
        merchant_db = _sb.table("global_merchant_intelligence").select("*").execute().data or []
        merchant_name, merchant_id, score, extract_meta = extract_merchant(merchant_candidate, merchant_db)
        
        # Use extracted merchant or fall back to candidate
        final_merchant_name = merchant_name or merchant_candidate or "Unknown"
        final_merchant_id = merchant_id or ""
        
        # Step 3: Extract amount and transaction details
        amount = parsing_meta.get("amount", 0.0)
        currency = parsing_meta.get("currency", "INR")
        transaction_type = parsing_meta.get("transaction_type", "DEBIT")
        payment_method = parsing_meta.get("payment_method", "UPI")
        
        # Step 4: Determine transaction timestamp
        if request.timestamp:
            try:
                # Use provided timestamp
                transaction_timestamp = datetime.fromisoformat(request.timestamp.replace('Z', '+00:00'))
            except ValueError:
                # Fall back to current time if invalid timestamp
                transaction_timestamp = datetime.now(timezone.utc)
        else:
            # Use current time if no timestamp provided
            transaction_timestamp = datetime.now(timezone.utc)
        
        # Step 5: Validate required fields
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid amount extracted from SMS"
            )
        
        # Step 6: Create transaction record
        transaction_id = str(uuid4())
        
        # build payload - only include columns we know exist in the current schema
        transaction_data = {
            "id": transaction_id,
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "merchant_name": final_merchant_name,
            "merchant_id": final_merchant_id,
            "transaction_type": transaction_type,
            # "payment_method" column is not guaranteed to exist; omit it to avoid errors
            "timestamp": transaction_timestamp.isoformat(),
            "raw_text": request.sms_text,
            "normalized_text": normalized_text,
            "parsing_metadata": parsing_meta,
            # additional fields such as sms_sender may not exist in all schemas
            # omit them if they are absent in the database
            "is_processed": False,  # Will be processed by auto_categorize later
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Insert transaction into database
        insert_result = _sb.table("transactions").insert(transaction_data).execute()
        
        if not insert_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create transaction record"
            )

        # schedule categorization for this user in the background so the
        # endpoint returns quickly but the pipeline is triggered immediately
        if background_tasks is not None:
            def _enqueue_categorization(uid: str):
                try:
                    from backend_supabase import auto_categorize
                except ImportError:
                    # fallback if import path isn't on PYTHONPATH; try manual
                    import sys
                    sys.path.insert(0, os.getcwd())
                    from backend_supabase import auto_categorize
                auto_categorize.run_auto_categorization(user_filter=uid)

            background_tasks.add_task(_enqueue_categorization, user_id)

        return SMSIngestResponse(
            transaction_id=transaction_id,
            status="success",
            merchant_name=final_merchant_name,
            amount=amount,
            transaction_type=transaction_type,
            message=f"Transaction created successfully for {final_merchant_name}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the error and return a generic error response
        print(f"SMS ingestion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during SMS processing: {str(e)}"
        )