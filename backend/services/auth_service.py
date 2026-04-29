"""
JWT authentication + password hashing for DocGen.

Design decisions:
- Tokens are 24-hour HS256 JWTs (suitable for internal tools).
- get_current_user raises 401 on any problem — use for protected endpoints.
- get_current_user_optional returns None silently — use where auth is preferred
  but not strictly required (e.g. generation endpoints that log the creator).
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from models.database import get_db, User, ProjectMember

SECRET_KEY = os.getenv("SECRET_KEY", "docgen-secret-2024")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


# ── Password ───────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ────────────────────────────────────────────────────────────────────────

def create_access_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── FastAPI dependencies ───────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Raises HTTP 401 if token is missing, invalid, or expired."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = _decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns None silently if no/bad token — for endpoints that work with or without auth."""
    if not credentials:
        return None
    try:
        payload = _decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.id == int(user_id)).first()
    except Exception:
        return None


def require_role(*roles: str):
    """Factory: returns a dependency that enforces one of the given roles."""
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role: {' or '.join(roles)}. Your role: {user.role}",
            )
        return user
    return _check


require_admin = require_role("admin")
require_admin_or_approver = require_role("admin", "approver")


def require_project_role(*roles: str):
    """
    Factory: returns a FastAPI dependency that verifies the current user has
    one of the given roles within the project identified by `project_id` path/query param.
    Global admins bypass the project-level check automatically.
    """
    async def _check(
        project_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> tuple[User, str]:
        if user.role == "admin":
            return user, "owner"   # admins have full access to every project
        membership = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="You are not a member of this project")
        if roles and membership.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires project role: {' or '.join(roles)}. Your role: {membership.role}",
            )
        return user, membership.role
    return _check


def get_user_project_ids(user: User, db) -> list[int]:
    """Return IDs of all projects the user is a member of (admin sees all)."""
    if user.role == "admin":
        from models.database import Project
        return [p.id for p in db.query(Project).all()]
    return [
        m.project_id
        for m in db.query(ProjectMember).filter(ProjectMember.user_id == user.id).all()
    ]
