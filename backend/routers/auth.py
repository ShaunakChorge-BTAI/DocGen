"""
Authentication router.

Registration policy:
  - If no users exist → anyone may register (first user becomes admin automatically).
  - If users exist → only an admin may create new accounts (invite-only).

This prevents open sign-up on a running instance while still allowing
easy first-time setup with zero configuration.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.database import get_db, User
from models.schemas import RegisterRequest, LoginRequest, TokenResponse, UserRecord
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_optional,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRecord)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    total_users = db.query(User).count()

    if total_users > 0:
        # Only an admin can create additional accounts — but we can't require
        # auth via Depends here because the first call has no token.
        # We accept an Authorization header manually through optional auth,
        # then enforce role.
        raise HTTPException(
            status_code=403,
            detail="Registration is admin-invite only. Ask an admin to create your account.",
        )

    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    role = "admin" if total_users == 0 else (req.role or "author")
    user = User(
        name=req.name,
        email=req.email,
        password_hash=hash_password(req.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/register/invite", response_model=UserRecord)
def admin_invite(
    req: RegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin-only endpoint to create additional user accounts."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        name=req.name,
        email=req.email,
        password_hash=hash_password(req.password),
        role=req.role or "author",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return TokenResponse(access_token=create_access_token(user))


@router.get("/me", response_model=UserRecord)
def me(current_user: User = Depends(get_current_user)):
    return current_user
