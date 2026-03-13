"""
User routes
-----------
POST /api/v1/user/login    — login with email/password, returns JWT
GET  /api/v1/user/profile  — return basic profile info
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import create_client
import os
from dotenv import load_dotenv

from backend_api.auth import get_current_user

load_dotenv()
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

router = APIRouter(prefix="/user", tags=["User"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest):
    """
    Login with email and password.
    Returns JWT token for subsequent authenticated requests.
    """
    try:
        auth_response = _sb.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if auth_response.user and auth_response.session:
            return LoginResponse(
                access_token=auth_response.session.access_token,
                token_type="bearer",
                user_id=str(auth_response.user.id),
                email=auth_response.user.email
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get("/profile")
def user_profile(user_id: str = Depends(get_current_user)):
    row = (
        _sb.table("users")
        .select("id, name, email, created_at")
        .eq("id", user_id)
        .limit(1)
        .execute()
        .data or []
    )
    if not row:
        return {}
    r = row[0]
    return {
        "user_id": r.get("id"),
        "name": r.get("name"),
        "email": r.get("email"),
        "joined_at": r.get("created_at"),
    }
