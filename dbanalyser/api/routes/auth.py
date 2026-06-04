"""
REST routes — /auth
JWT authentication backed by the users PostgreSQL table (Phase G).

Endpoints
---------
  POST /auth/register          Create new organisation + first admin user
  POST /auth/token             Login → access token
  GET  /auth/me                Caller identity
  POST /auth/invite            Admin: invite user by email
  GET  /auth/invitations       Admin: list pending invitations
  POST /auth/accept-invite     Accept an invitation + set password
  POST /auth/change-password   Change own password
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])

_bearer = HTTPBearer(auto_error=False)


# ─── Request / response schemas ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    org_name:  str
    username:  str
    email:     str
    password:  str


class TokenRequest(BaseModel):
    username: str
    password: str
    org_slug: Optional[str] = None   # optional; omit for single-org dev mode


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    role:         str
    org_id:       Optional[int] = None
    username:     str


class MeResponse(BaseModel):
    username: str
    email:    str
    role:     str
    org_id:   Optional[int] = None
    user_id:  Optional[int] = None


class InviteRequest(BaseModel):
    email:         str
    role:          str = "viewer"
    expires_hours: int = 48


class AcceptInviteRequest(BaseModel):
    token:    str
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_cfg_auth():
    try:
        from dbanalyser.api.main import _get_cfg
        return _get_cfg().auth
    except Exception:
        return None


def _decode(token: str):
    try:
        from dbanalyser.api.auth_rbac import decode_token
        cfg = _get_cfg_auth()
        if not cfg:
            return None
        return decode_token(token, cfg.secret_key, cfg.algorithm)
    except Exception:
        return None


def _require_token(credentials: Optional[HTTPAuthorizationCredentials]) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Missing Bearer token",
                            headers={"WWW-Authenticate": "Bearer"})
    payload = _decode(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token")
    return payload


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(req: RegisterRequest):
    """Create a new organisation and its first admin user. Returns a JWT token."""
    from dbanalyser.api.auth_rbac import hash_password, create_access_token, build_token_payload
    from dbanalyser.db.org_repository import (
        create_organization, create_user, slugify, get_organization_by_slug,
    )
    from dbanalyser.db.models import Organization, User

    slug = slugify(req.org_name)
    if get_organization_by_slug(slug):
        raise HTTPException(status_code=400,
                            detail=f"Organisation '{req.org_name}' already exists.")
    try:
        org_id  = create_organization(Organization(name=req.org_name, slug=slug))
        user_id = create_user(User(
            org_id=org_id, username=req.username, email=req.email,
            password_hash=hash_password(req.password), role="admin",
        ))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Registration failed: {exc}")

    user_row = {"id": user_id, "org_id": org_id, "username": req.username,
                "email": req.email, "role": "admin"}
    cfg = _get_cfg_auth()
    token = create_access_token(
        data=build_token_payload(user_row),
        secret_key=getattr(cfg, "secret_key", "dev-secret"),
        algorithm=getattr(cfg, "algorithm", "HS256"),
        expires_minutes=getattr(cfg, "token_expire_minutes", 480),
    )
    return {"access_token": token, "token_type": "bearer", "role": "admin",
            "org_id": org_id, "username": req.username, "org_slug": slug}


@router.post("/token", response_model=TokenResponse)
def login(req: TokenRequest):
    """Exchange username + password for a JWT access token."""
    from dbanalyser.api.auth_rbac import verify_password, create_access_token, build_token_payload
    from dbanalyser.db.org_repository import (
        get_organization_by_slug, get_user_by_username, update_user_last_login,
    )

    cfg = _get_cfg_auth()

    # ── DB-based auth (Phase G) ──────────────────────────────────────────────
    try:
        import logging
        log = logging.getLogger("dbanalyser.api.auth")
        user = None
        if req.org_slug:
            org = get_organization_by_slug(req.org_slug)
            if org:
                user = get_user_by_username(org["id"], req.username)
        else:
            from dbanalyser.db.connection import get_cursor
            with get_cursor() as cur:
                cur.execute(
                    "SELECT * FROM users WHERE username=%s AND is_active=TRUE LIMIT 1",
                    (req.username,))
                row = cur.fetchone()
                user = dict(row) if row else None
                log.info(f"DB lookup for user '{req.username}': {'found' if user else 'not found'}")

        if user and verify_password(req.password, user["password_hash"]):
            log.info(f"Login successful for user '{req.username}'")
            update_user_last_login(user["id"])
            token = create_access_token(
                data=build_token_payload(user),
                secret_key=getattr(cfg, "secret_key", "dev-secret"),
                algorithm=getattr(cfg, "algorithm", "HS256"),
                expires_minutes=getattr(cfg, "token_expire_minutes", 480),
            )
            return TokenResponse(access_token=token, role=user["role"],
                                 org_id=user["org_id"], username=user["username"])
        elif user:
            log.warning(f"Password mismatch for user '{req.username}'")
    except HTTPException:
        raise
    except Exception as e:
        import logging
        log = logging.getLogger("dbanalyser.api.auth")
        log.error(f"Auth error: {e}", exc_info=True)
        pass  # fall through to YAML-based legacy auth

    # ── Legacy YAML-based auth ───────────────────────────────────────────────
    if not cfg or not getattr(cfg, "enabled", False):
        raise HTTPException(status_code=501, detail="Authentication is not enabled.")

    matched = next((u for u in getattr(cfg, "users", [])
                    if u.username == req.username), None)
    if not matched or not verify_password(req.password, matched.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.",
                            headers={"WWW-Authenticate": "Bearer"})

    token = create_access_token(
        data={"sub": matched.username, "username": matched.username,
              "role": matched.role, "org_id": None, "user_id": None, "email": ""},
        secret_key=cfg.secret_key, algorithm=cfg.algorithm,
        expires_minutes=cfg.token_expire_minutes,
    )
    return TokenResponse(access_token=token, role=matched.role,
                         org_id=None, username=matched.username)


@router.get("/me", response_model=MeResponse)
def get_me(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)):
    """Return the identity of the caller."""
    cfg = _get_cfg_auth()
    if not cfg or not getattr(cfg, "enabled", False):
        return MeResponse(username="anonymous", email="", role="admin")

    payload = _require_token(credentials)
    return MeResponse(
        username=payload.get("sub", "unknown"),
        email=payload.get("email", ""),
        role=payload.get("role", "viewer"),
        org_id=payload.get("org_id"),
        user_id=payload.get("user_id"),
    )


@router.post("/invite", status_code=201)
def invite_user(
    req: InviteRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
):
    """Admin: create an invitation token for a new user."""
    payload = _require_token(credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required.")
    org_id = payload.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No org context in token.")
    from dbanalyser.db.org_repository import create_invitation
    inv = create_invitation(org_id, req.email, req.role, req.expires_hours)
    return {"ok": True, "token": inv["token"], "expires_at": str(inv["expires_at"])}


@router.get("/invitations")
def list_invitations(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
):
    """Admin: list all invitations for the org."""
    payload = _require_token(credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required.")
    org_id = payload.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No org context in token.")
    from dbanalyser.db.org_repository import list_invitations as _list
    return {"invitations": _list(org_id)}


@router.post("/accept-invite", status_code=201)
def accept_invite(req: AcceptInviteRequest):
    """Accept an invitation and create a new user account."""
    from dbanalyser.api.auth_rbac import hash_password, create_access_token, build_token_payload
    from dbanalyser.db.org_repository import (
        get_invitation_by_token, accept_invitation, create_user,
    )
    from dbanalyser.db.models import User

    inv = get_invitation_by_token(req.token)
    if not inv:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation.")
    if inv.get("accepted_at"):
        raise HTTPException(status_code=400, detail="Invitation already accepted.")

    try:
        user_id = create_user(User(
            org_id=inv["org_id"], username=req.username, email=inv["email"],
            password_hash=hash_password(req.password), role=inv["role"],
        ))
        accept_invitation(req.token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create account: {exc}")

    user_row = {"id": user_id, "org_id": inv["org_id"], "username": req.username,
                "email": inv["email"], "role": inv["role"]}
    cfg = _get_cfg_auth()
    token = create_access_token(
        data=build_token_payload(user_row),
        secret_key=getattr(cfg, "secret_key", "dev-secret"),
        algorithm=getattr(cfg, "algorithm", "HS256"),
        expires_minutes=getattr(cfg, "token_expire_minutes", 480),
    )
    return {"access_token": token, "token_type": "bearer", "role": inv["role"],
            "org_id": inv["org_id"], "username": req.username}


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
):
    """Change the caller's own password."""
    payload = _require_token(credentials)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="No user_id in token (legacy auth).")

    from dbanalyser.api.auth_rbac import verify_password, hash_password
    from dbanalyser.db.org_repository import get_user_by_id, update_user_password

    user = get_user_by_id(user_id)
    if not user or not verify_password(req.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    update_user_password(user_id, hash_password(req.new_password))
    return {"ok": True, "message": "Password updated."}
