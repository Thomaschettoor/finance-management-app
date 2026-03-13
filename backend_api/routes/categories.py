"""
Categories routes
-----------------
GET /api/v1/categories   — list all available categories
"""

from fastapi import APIRouter, Depends
from supabase import create_client
import os
from dotenv import load_dotenv

from backend_api.auth import get_current_user

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/", summary="List all categories")
def list_categories(user_id: str = Depends(get_current_user)):
    """
    Returns all available transaction categories.
    Used by the mobile app to populate category pickers.

    The original `categories` table does not exist in some deployments;
    instead we fall back to `master_categories` which holds the same data.
    """
    # We only use master_categories in this deployment; using a single table simplifies the code.
    rows = (
        _sb.table("master_categories")
        .select("id, name, description")
        .order("name")
        .execute()
        .data or []
    )
    # ensure icon/color fields exist for compatibility with clients
    for r in rows:
        r.setdefault("icon", "")
        r.setdefault("color", "#000000")
    return {"categories": rows, "total": len(rows)}
