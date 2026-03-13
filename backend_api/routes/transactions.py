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

def _fetch_category_map() -> dict[str, str]:
    """Load category UUID→name mapping from master_categories (or categories)."""
    # prefer master_categories which is always present
    try:
        rows = (_sb.table("master_categories").select("id, name").execute().data or [])
    except Exception:
        # fallback if schema is old
        rows = (_sb.table("categories").select("id, name").execute().data or [])
    return {r["id"]: r.get("name", "") for r in rows}


def _merge_transaction(txn: dict, cat: Optional[dict]) -> dict:
    """Merge a transaction row with its categorization row into one response dict."""
    return {
        "id":                 txn["id"],
        "amount":             txn.get("amount"),
        "merchant_name":      txn.get("merchant_name") or "",
        "transaction_date":   txn.get("timestamp") or txn.get("created_at"),
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
    limit:       int      = Query(20, ge=1, le=100, description="Items per page"),
    category:    Optional[str] = Query(None, description="Filter by category UUID"),
    search:      Optional[str] = Query(None, description="Search merchant name"),
    sort:        Optional[str] = Query("recent", description="Sort options: recent | highest"),
    min_amount:  Optional[float] = Query(None, description="Minimum transaction amount"),
    max_amount:  Optional[float] = Query(None, description="Maximum transaction amount"),
    start_date:  Optional[str] = Query(None, description="ISO start date"),
    end_date:    Optional[str] = Query(None, description="ISO end date"),
    month:       Optional[int]   = Query(None, ge=1, le=12, description="Optional month filter (requires year)"),
    year:        Optional[int]   = Query(None, ge=2000, description="Optional year filter (requires month)"),
    tx_type:     Optional[str] = Query(None, description="credit|debit"),
    user_id:     str = Depends(get_current_user),
):
    """
    Paginated and filterable transaction list for the authenticated user.

    Supports search, category filter, amount range, date range, type (credit/debit),
    and sorting. The response shape is standardized for the mobile app.
    """
    offset = (page - 1) * limit

    # pre-load categories mapping so we can return names instead of raw UUIDs
    category_map = _fetch_category_map()

    # build base query
    q = (
        _sb.table("transactions")
        .select("id, amount, merchant_name, timestamp, created_at, "
                "raw_text, is_processed, transaction_type")
        .eq("user_id", user_id)
    )

    # date filters (use timestamp column). month/year pair takes precedence over
    # raw start_date/end_date to make it easy to request a whole calendar month.
    if month is not None or year is not None:
        if month is None or year is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both month and year must be provided when filtering by month",
            )
        # construct beginning of requested month and the next month
        try:
            start = datetime(year, month, 1, tzinfo=timezone.utc)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid month/year combination",
            )
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        q = q.gte("timestamp", start.isoformat()).lt("timestamp", end.isoformat())
    else:
        if start_date:
            q = q.gte("timestamp", start_date)
        if end_date:
            q = q.lte("timestamp", end_date)

    # amount filters
    if min_amount is not None:
        q = q.gte("amount", min_amount)
    if max_amount is not None:
        q = q.lte("amount", max_amount)

    # type filter (transaction_type column assumed to be "CREDIT"/"DEBIT")
    if tx_type:
        tval = "CREDIT" if tx_type.lower() == "credit" else "DEBIT"
        q = q.eq("transaction_type", tval)

    # merchant search
    if search:
        q = q.ilike("merchant_name", f"%{search}%")

    # sorting
    if sort == "highest":
        q = q.order("amount", desc=True)
    else:
        # default and recent sort both use timestamp descending
        q = q.order("timestamp", desc=True)

    # pagination
    q = q.range(offset, offset + limit - 1)

    txns = q.execute().data or []

    if not txns:
        return {"page": page, "limit": limit, "total": 0, "transactions": []}

    # fetch categorizations
    ids = [t["id"] for t in txns]
    cat_map = _fetch_categorizations_map(ids)

    out = []
    for txn in txns:
        cat = cat_map.get(txn["id"])
        # post-join filters for category
        if category and (not cat or cat.get("primary_category_id") != category):
            continue
        merged = _merge_transaction(txn, cat)
        # base object contains original fields for compatibility
        item = {
            "id": merged.get("id"),
            "amount": merged.get("amount"),
            "merchant_name": merged.get("merchant_name"),
            "transaction_date": merged.get("transaction_date"),
            "category_id": merged.get("category_id"),
            # new convenience fields
            "transaction_id": merged.get("id"),
            "merchant": merged.get("merchant_name"),
            "category": merged.get("category_id"),
            "category_name": category_map.get(merged.get("category_id")) if merged.get("category_id") else None,
            "type": "credit" if merged.get("amount", 0) >= 0 else "debit",
            "date": merged.get("transaction_date"),
        }
        out.append(item)

    total = len(out)
    # include per_page for backwards compatibility
    return {
        "page": page,
        "limit": limit,
        "per_page": limit,
        "total": total,
        "transactions": out,
    }

# ── GET /transactions/merchants ───────────────────────────────────────────────

@router.get("/merchants", summary="Merchant autocomplete suggestions")
def merchant_suggestions(
    q: str = Query(..., description="Search query for merchant name"),
    user_id: str = Depends(get_current_user),
):
    """
    Return distinct merchant names matching the query (case‑insensitive), up to 10 results.
    """
    rows = (
        _sb.table("transactions")
        .select("merchant_name")
        .eq("user_id", user_id)
        .ilike("merchant_name", f"%{q}%")
        .limit(100)
        .execute()
        .data or []
    )
    names = []
    seen = set()
    for r in rows:
        name = r.get("merchant_name")
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
            if len(names) >= 10:
                break
    return {"merchant_names": names}


# ── POST /transactions ───────────────────────────────────────────────────────

class CreateTransactionRequest(BaseModel):
    merchant:     str
    amount:       float
    category_id:  Optional[str]
    date:         Optional[str]
    notes:        Optional[str]

class CreateTransactionResponse(BaseModel):
    transaction_id: str
    status: str

@router.post("/", summary="Create a new transaction", response_model=CreateTransactionResponse)
def create_transaction(
    body: CreateTransactionRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Manual transaction creation. Amount positive -> credit, negative -> debit.
    """
    tx_type = "CREDIT" if body.amount >= 0 else "DEBIT"
    ts_val = body.date or datetime.now(timezone.utc).isoformat()
    payload = {
        "user_id": user_id,
        "merchant_name": body.merchant,
        "amount": str(body.amount),
        "transaction_type": tx_type,
        "transaction_date": ts_val,
        "timestamp": ts_val,
        "notes": body.notes or "",
    }

    try:
        res = _sb.table("transactions").insert(payload).execute().data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")
    txn_id = res[0].get("id") if res else None
    return {"transaction_id": txn_id, "status": "created"}

# ── GET /transactions/{id} ────────────────────────────────────────────────────

@router.get("/{transaction_id}", summary="Get a single transaction")
def get_transaction(
    transaction_id: str,
    user_id: str = Depends(get_current_user),
):
    """Returns full detail for one transaction, including categorization."""
    # select all columns; some environments may not have all fields (notes, payment_method, source)
    rows = (
        _sb.table("transactions")
        .select("*")
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
    merged = _merge_transaction(txn, cat)
    cat_id = merged.get("category_id")
    category_name = None
    if cat_id:
        # load map lazily
        cmap = _fetch_category_map()
        category_name = cmap.get(cat_id)
    return {
        "transaction_id": merged["id"],
        "merchant": merged["merchant_name"],
        "amount": merged.get("amount"),
        "category": merged.get("category_id"),
        "category_name": category_name,
        "date": merged.get("transaction_date"),
        # optional columns may not exist in every schema
        "notes": txn.get("notes"),
        "payment_method": txn.get("payment_method"),
        "source": txn.get("source"),
    }


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
    ts = txn.get("timestamp") or txn.get("created_at")
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
