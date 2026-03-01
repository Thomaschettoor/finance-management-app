"""
Authentication dependency for the FastAPI layer.

Every protected endpoint uses `Depends(get_current_user)`.

Flow:
  1. Client sends:  Authorization: Bearer <supabase_jwt>
  2. We call supabase.auth.get_user(jwt) — Supabase validates the token
     and returns the user object (or raises an error if invalid/expired).
  3. We extract user_id and return it as a plain string.
     Routes receive only user_id — no raw token in business logic.

No custom JWT secret management needed: Supabase handles verification.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

_supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """
    FastAPI dependency. Returns the authenticated user_id (UUID string).

    Raises HTTP 401 if the token is missing, invalid, or expired.
    """
    token = credentials.credentials
    try:
        resp = _supabase.auth.get_user(token)
        if resp is None or resp.user is None:
            raise ValueError("no user in response")
        return str(resp.user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
