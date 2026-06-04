"""
JWT Authentication and Role-Based Access Control
=================================================
Provides JWT token creation/verification and FastAPI dependency factories.

Roles (least → most privileged)
--------------------------------
  viewer   — read findings, runs, trend, databases
  analyst  — viewer + trigger analysis runs
  admin    — analyst + manage registry, suppress/acknowledge findings

Optional dependency: PyJWT (pip install PyJWT)  or  python-jose (pip install python-jose)
Optional dependency: bcrypt (pip install bcrypt)

If auth.enabled = false in config, all auth checks pass automatically.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger(__name__)

ROLE_RANK = {"viewer": 0, "analyst": 1, "admin": 2}


# ─── Lazy imports ─────────────────────────────────────────────────────────────

def _get_jwt():
    try:
        import jwt as _jwt
        return _jwt
    except ImportError:
        pass
    try:
        from jose import jwt as _jwt  # type: ignore
        return _jwt
    except ImportError:
        raise ImportError(
            "JWT library not found. Install: pip install PyJWT  "
            "or  pip install python-jose"
        )


def _get_bcrypt():
    try:
        import bcrypt
        return bcrypt
    except ImportError:
        raise ImportError(
            "bcrypt not found. Install: pip install bcrypt"
        )


# ─── Token helpers ────────────────────────────────────────────────────────────

def create_access_token(
    data: dict,
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 480,
) -> str:
    """Encode a JWT access token."""
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    jwt = _get_jwt()
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> Optional[dict]:
    """Decode a JWT token.  Returns None on any error."""
    try:
        jwt = _get_jwt()
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except Exception as exc:
        log.debug("Token decode failed: %s", exc)
        return None


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the password."""
    bcrypt = _get_bcrypt()
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if password matches the stored bcrypt hash."""
    try:
        bcrypt = _get_bcrypt()
        return bool(bcrypt.checkpw(password.encode(), password_hash.encode()))
    except Exception:
        return False


# ─── FastAPI dependency factory ───────────────────────────────────────────────

def make_rbac_dependency(cfg_auth, required_role: str = "viewer"):
    """
    Return a FastAPI ``Depends`` that validates JWT tokens and enforces role.

    If ``cfg_auth.enabled`` is False the dependency is a no-op (always passes).

    Args:
        cfg_auth      : AuthConfig instance from Settings.
        required_role : Minimum role needed ("viewer" | "analyst" | "admin").

    Usage::

        AdminRequired = make_rbac_dependency(cfg.auth, required_role="admin")

        @router.delete("/databases/{name}", dependencies=[AdminRequired])
        def delete_db(name: str): ...
    """
    from fastapi import HTTPException, Security, status
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    _bearer = HTTPBearer(auto_error=False)

    def _check(
        credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
    ):
        if not getattr(cfg_auth, "enabled", False):
            # Auth is disabled — allow everything (dev mode)
            return {
                "sub": "anonymous", "username": "anonymous",
                "role": "admin", "org_id": None, "user_id": None, "email": "",
            }

        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = decode_token(
            credentials.credentials,
            secret_key=cfg_auth.secret_key,
            algorithm=getattr(cfg_auth, "algorithm", "HS256"),
        )
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        user_role = payload.get("role", "viewer")
        if ROLE_RANK.get(user_role, -1) < ROLE_RANK.get(required_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(f"This endpoint requires '{required_role}' role. "
                        f"Your role: '{user_role}'."),
            )
        # Normalise: ensure 'username' key exists alongside 'sub'
        payload.setdefault("username", payload.get("sub", "unknown"))
        return payload

    from fastapi import Depends
    return Depends(_check)


def build_token_payload(user: dict) -> dict:
    """Build JWT payload from a users-table row."""
    return {
        "sub":      user["username"],
        "username": user["username"],
        "email":    user.get("email", ""),
        "role":     user.get("role", "viewer"),
        "org_id":   user.get("org_id"),
        "user_id":  user.get("id"),
    }
