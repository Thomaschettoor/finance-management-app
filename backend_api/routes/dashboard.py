"""
Dashboard routes
----------------
GET  /api/v1/dashboard/summary          — financial overview (name, totals)
GET  /api/v1/dashboard/recent_transactions — latest transactions for home screen
"""
from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, Query

from supabase import create_client
import os
from dotenv import load_dotenv

from backend_api.auth import get_current_user

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(user_id: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Return overview data needed on home screen."""
    # get user name & currency if we have a users table schema that
    # contains those columns.  Some deployments (test harness) only insert
    # id/email and lack `name`/`currency` fields, which would cause a
    # PostgREST APIError.  Wrap in try/except and fall back to safe defaults.
    user_name = ""
    currency = ""
    try:
        user_row = (
            _sb.table("users").select("id, name, currency").eq("id", user_id).limit(1).execute().data or []
        )
        if user_row:
            user_name = user_row[0].get("name") or user_row[0].get("email") or ""
            currency = user_row[0].get("currency") or ""
    except Exception:
        # missing column or other DB issue; just return empty strings
        pass

    # calculate boundaries for the current month (UTC)
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # next month = first of following month; used for < comparison so that the
    # period is [start_of_month, start_of_next_month)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)

    # fetch transaction_type so we can distinguish credits vs debits; many
    # records store debit amounts as positive and rely on the transaction_type
    # field for direction. if the column doesn't exist we fall back to sign-based
    # behaviour as a last resort.
    q = (
        _sb.table("transactions")
        .select("amount, transaction_type")
        .eq("user_id", user_id)
        .gte("timestamp", start.isoformat())
        .lt("timestamp", next_month.isoformat())
    )
    txns = q.execute().data or []

    total_credit = 0.0
    total_debit = 0.0
    for t in txns:
        amt = float(t.get("amount") or 0)
        ttype = (t.get("transaction_type") or "").upper()
        if ttype == "CREDIT":
            total_credit += amt
        elif ttype == "DEBIT":
            total_debit += amt
        else:
            # fallback when transaction_type missing: use sign
            if amt >= 0:
                total_credit += amt
            else:
                total_debit += amt
    return {
        "user_name": user_name,
        "total_credit": round(total_credit, 2),
        "total_debit": round(total_debit, 2),
        "transaction_count": len(txns),
        "currency": currency,
    }


@router.get("/recent_transactions")
def recent_transactions(
    limit: int = Query(5, ge=1, le=50),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return most recent N transactions for the home page.

    This endpoint is used by the front‑end/dashboard to populate the list of
    latest activity.  The Android client refers to it via
    ``ApiConfig.RECENT_TRANSACTIONS`` and the API client setup docs
    (`API_CLIENT_SETUP.md`) show how to call it.

    The route intentionally returns a simple JSON object with a
    ``transactions`` array.  If the database call fails for any reason we
    catch the exception and return an empty list rather than letting an
    uncaught error bubble up as a 500.  We also attempt to coerce numeric
    fields safely so malformed data doesn't crash the server.
    """
    try:
        rows = (
            _sb.table("transactions")
            .select(
                "id, merchant_name, amount, category_id, timestamp as transaction_date, created_at"
            )
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        # Log to console for debugging; return an empty result so the UI
        # can still render (it should show a "no recent activity" message).
        print(f"recent_transactions query failed: {exc}")
        return {"transactions": [], "error": str(exc)}

    items: List[Dict[str, Any]] = []
    for r in rows:
        # amount might be stored as string or malformed; coerce safely
        try:
            amt = float(r.get("amount") or 0)
        except Exception:
            amt = 0.0

        items.append(
            {
                "transaction_id": r.get("id"),
                "merchant": r.get("merchant_name"),
                "category": r.get("category_id"),
                "amount": amt,
                "type": "credit" if amt >= 0 else "debit",
                "date": r.get("transaction_date") or r.get("created_at"),
            }
        )
    return {"transactions": items}
