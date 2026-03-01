"""
Transaction routes
------------------
GET  /api/v1/transactions                    — paginated transaction list
GET  /api/v1/transactions/{id}               — single transaction detail
GET  /api/v1/transactions/{id}/suggestions   — behavioral Top-3 suggestions
POST /api/v1/transactions/{id}/confirm       — user confirms a category
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from supabase import create_client
import os
from dotenv import load_dotenv

from backend_api.auth import get_current_user
from backend_supabase.behavior_suggestion_engine import (
    generate_suggestions,
    confirm_category,
)

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

router = APIRouter(prefix="/transactions", tags=["Transactions"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _merge_transaction(txn: dict, cat: Optional[dict]) -> dict:
    """Merge a transaction row with its categorization row into one response dict."""
    return {
        "id":                 txn["id"],
        "amount":             txn.get("amount"),
        "merchant_name":      txn.get("merchant_name") or "",
        "transaction_date":   txn.get("transaction_date") or txn.get("created_at"),
        "raw_text":           txn.get("raw_text") or "",
        "is_processed":       txn.get("is_processed", False),
        # categorization fields (None if not yet categorized)
        "category_id":        cat["primary_category_id"]  if cat else None,
        "confidence":         cat["primary_confidence"]    if cat else None,
        "prediction_source":  cat["prediction_source"]     if cat else None,
        "prediction_status":  cat["prediction_status"]     if cat else None,
        "behavioral_suggestions": (cat or {}).get("behavioral_suggestions"),
    }


def _fetch_categorizations_map(txn_ids: list[str]) -> dict[str, dict]:
    """Return {transaction_id: categorization_row} for a list of txn ids."""
    if not txn_ids:
        return {}
    rows = (
        _sb.table("transaction_categorizations")
        .select("transaction_id, primary_category_id, primary_confidence, "
                "prediction_source, prediction_status, behavioral_suggestions")
        .in_("transaction_id", txn_ids)
        .execute()
        .data or []
    )
    return {r["transaction_id"]: r for r in rows}


# ── GET /transactions ─────────────────────────────────────────────────────────

@router.get("/", summary="List transactions (paginated)")
def list_transactions(
    page:        int      = Query(1, ge=1, description="Page number (1-based)"),
    per_page:    int      = Query(20, ge=1, le=100, description="Items per page"),
    category_id: Optional[str] = Query(None, description="Filter by category UUID"),
    source:      Optional[str] = Query(None, description="Filter by prediction_source "
                                        "(CONFIDENT_MERCHANT | UNCLASSIFIED | USER_CONFIRMED)"),
    user_id:     str = Depends(get_current_user),
):
    """
    Returns a paginated list of the authenticated user's transactions,
    each enriched with its categorization data and behavioral suggestions
    (where available).
    """
    offset = (page - 1) * per_page

    # 1. Fetch transactions for this user
    q = (
        _sb.table("transactions")
        .select("id, amount, merchant_name, transaction_date, created_at, "
                "raw_text, is_processed")
        .eq("user_id", user_id)
        .order("transaction_date", desc=True)
        .range(offset, offset + per_page - 1)
    )
    txns = q.execute().data or []

    if not txns:
        return {"page": page, "per_page": per_page, "total": 0, "transactions": []}

    # 2. Fetch categorizations in one query
    cat_map = _fetch_categorizations_map([t["id"] for t in txns])

    # 3. Apply optional filters (category_id, source) - post-join filter
    results = []
    for txn in txns:
        cat = cat_map.get(txn["id"])
        if category_id and (not cat or cat.get("primary_category_id") != category_id):
            continue
        if source and (not cat or cat.get("prediction_source") != source):
            continue
        results.append(_merge_transaction(txn, cat))

    return {
        "page":         page,
        "per_page":     per_page,
        "count":        len(results),
        "transactions": results,
    }


# ── GET /transactions/{id} ────────────────────────────────────────────────────

@router.get("/{transaction_id}", summary="Get a single transaction")
def get_transaction(
    transaction_id: str,
    user_id: str = Depends(get_current_user),
):
    """Returns full detail for one transaction, including categorization."""
    rows = (
        _sb.table("transactions")
        .select("id, amount, merchant_name, transaction_date, created_at, "
                "raw_text, is_processed, parsing_metadata, merchant_id")
        .eq("id", transaction_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    txn = rows[0]
    cat_map = _fetch_categorizations_map([transaction_id])
    cat = cat_map.get(transaction_id)
    return _merge_transaction(txn, cat)


# ── GET /transactions/{id}/suggestions ───────────────────────────────────────

@router.get("/{transaction_id}/suggestions", summary="Get Top-3 category suggestions")
def get_suggestions(
    transaction_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Returns Top-3 behavioral category suggestions for an UNCLASSIFIED transaction.

    If suggestions are already stored in transaction_categorizations, returns those.
    Otherwise calls the behavior engine live (requires user to have ≥ 5 transactions
    of history — engine returns empty list if not).

    Always returns requires_user_confirmation = true.
    Only meaningful for UNCLASSIFIED transactions.
    """
    # Verify ownership
    txn_rows = (
        _sb.table("transactions")
        .select("id, amount, transaction_date, created_at")
        .eq("id", transaction_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data or []
    )
    if not txn_rows:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    txn = txn_rows[0]

    # Check if suggestions already stored
    cat_rows = (
        _sb.table("transaction_categorizations")
        .select("prediction_source, behavioral_suggestions")
        .eq("transaction_id", transaction_id)
        .limit(1)
        .execute()
        .data or []
    )

    if cat_rows:
        cat = cat_rows[0]
        if cat.get("prediction_source") not in ("UNCLASSIFIED",):
            return {
                "transaction_id":              transaction_id,
                "suggestions":                 [],
                "requires_user_confirmation":  False,
                "note": f"Transaction is already {cat['prediction_source']}.",
            }
        existing = cat.get("behavioral_suggestions")
        if existing and existing.get("suggestions"):
            return existing

    # Generate live
    ts = txn.get("transaction_date") or txn.get("created_at")
    return generate_suggestions(
        user_id=user_id,
        transaction={
            "transaction_id": transaction_id,
            "amount":         float(txn.get("amount") or 0),
            "timestamp":      ts,
        },
    )


# ── POST /transactions/{id}/confirm ──────────────────────────────────────────

class ConfirmRequest(BaseModel):
    category_id: str


@router.post("/{transaction_id}/confirm", summary="Confirm a category for a transaction")
def confirm_transaction_category(
    transaction_id: str,
    body: ConfirmRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Called when a user selects a category from the suggestions or manually picks one.

    - Updates transaction_categorizations (prediction_source = USER_CONFIRMED)
    - Rebuilds user_behavior_profiles for this (user, category) pair
    - Future suggestions for this user improve automatically
    """
    # Verify ownership
    rows = (
        _sb.table("transactions")
        .select("id")
        .eq("id", transaction_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    confirm_category(
        user_id=user_id,
        transaction_id=transaction_id,
        confirmed_category_id=body.category_id,
    )

    return {
        "success":        True,
        "transaction_id": transaction_id,
        "category_id":    body.category_id,
        "message":        "Category confirmed. Behavior profile updated.",
    }
