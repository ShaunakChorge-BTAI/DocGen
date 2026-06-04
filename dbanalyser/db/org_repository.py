"""
DBAnalyser — Organisation & User repository (Phase G — Multi-tenancy).
All SQL for organizations, users, assessment_configs, and invitations.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dbanalyser.db.connection import get_conn, get_cursor
from dbanalyser.db.models import AssessmentConfig, Invitation, Organization, User


# ─── Organizations ────────────────────────────────────────────────────────────

def create_organization(org: Organization) -> int:
    """Insert a new organisation. Returns the new id."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO organizations (name, slug, plan, is_active)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (org.name, org.slug, org.plan, org.is_active))
        return cur.fetchone()[0]


def get_organization(org_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM organizations WHERE id = %s", (org_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_organization_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM organizations WHERE slug = %s", (slug,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_organizations(active_only: bool = True) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        sql = "SELECT * FROM organizations"
        if active_only:
            sql += " WHERE is_active = TRUE"
        sql += " ORDER BY name"
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def update_organization(org_id: int, name: str = None, plan: str = None,
                        is_active: bool = None) -> bool:
    parts, params = [], []
    if name      is not None: parts.append("name = %s");      params.append(name)
    if plan      is not None: parts.append("plan = %s");      params.append(plan)
    if is_active is not None: parts.append("is_active = %s"); params.append(is_active)
    if not parts:
        return False
    params.append(org_id)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE organizations SET {', '.join(parts)}, updated_at=NOW() WHERE id = %s", params)
        return cur.rowcount > 0


def deactivate_organization(org_id: int) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE organizations SET is_active=FALSE, updated_at=NOW() WHERE id=%s", (org_id,))
        return cur.rowcount > 0


def slugify(name: str) -> str:
    """Convert org name to a url-safe slug. e.g. 'LTFS Corp' → 'ltfs-corp'"""
    import re
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# ─── Users ────────────────────────────────────────────────────────────────────

def create_user(user: User) -> int:
    """Insert a new user. Returns the new id."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO users (org_id, username, email, password_hash, role, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (user.org_id, user.username, user.email,
              user.password_hash, user.role, user.is_active))
        return cur.fetchone()[0]


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_user_by_username(org_id: int, username: str) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM users WHERE org_id = %s AND username = %s AND is_active = TRUE",
            (org_id, username))
        row = cur.fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Lookup user by email (cross-org — used for invitation acceptance)."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s AND is_active = TRUE", (email,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_users(org_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        sql = "SELECT id, org_id, username, email, role, is_active, last_login_at, created_at FROM users WHERE org_id = %s"
        if active_only:
            sql += " AND is_active = TRUE"
        sql += " ORDER BY username"
        cur.execute(sql, (org_id,))
        return [dict(r) for r in cur.fetchall()]


def update_user_role(user_id: int, role: str) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET role=%s, updated_at=NOW() WHERE id=%s", (role, user_id))
        return cur.rowcount > 0


def deactivate_user(user_id: int) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET is_active=FALSE, updated_at=NOW() WHERE id=%s", (user_id,))
        return cur.rowcount > 0


def update_user_last_login(user_id: int) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET last_login_at=NOW(), updated_at=NOW() WHERE id=%s", (user_id,))


def update_user_password(user_id: int, new_hash: str) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET password_hash=%s, updated_at=NOW() WHERE id=%s",
                    (new_hash, user_id))
        return cur.rowcount > 0


# ─── Invitations ──────────────────────────────────────────────────────────────

def create_invitation(org_id: int, email: str, role: str = "viewer",
                      expires_hours: int = 48) -> Dict[str, Any]:
    """Create an invitation token. Returns the invitation record."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO invitations (org_id, email, role, token, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, token, expires_at
        """, (org_id, email, role, token, expires_at))
        row = cur.fetchone()
        return {"id": row[0], "token": row[1], "expires_at": row[2],
                "email": email, "role": role, "org_id": org_id}


def get_invitation_by_token(token: str) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT i.*, o.name AS org_name, o.slug AS org_slug
            FROM invitations i
            JOIN organizations o ON o.id = i.org_id
            WHERE i.token = %s
        """, (token,))
        row = cur.fetchone()
        return dict(row) if row else None


def accept_invitation(token: str) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE invitations SET accepted_at = NOW()
            WHERE token = %s AND accepted_at IS NULL AND expires_at > NOW()
        """, (token,))
        return cur.rowcount > 0


def list_invitations(org_id: int) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM invitations WHERE org_id = %s ORDER BY created_at DESC
        """, (org_id,))
        return [dict(r) for r in cur.fetchall()]


# ─── Assessment Configs ───────────────────────────────────────────────────────

def upsert_assessment_config(cfg: AssessmentConfig) -> int:
    """Insert or update per-database assessment config. Returns row id."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO assessment_configs (org_id, db_registry_id, config_json)
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (org_id, db_registry_id) DO UPDATE
                SET config_json = EXCLUDED.config_json, updated_at = NOW()
            RETURNING id
        """, (cfg.org_id, cfg.db_registry_id, json.dumps(cfg.config_json)))
        return cur.fetchone()[0]


def get_assessment_config(org_id: int, db_registry_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM assessment_configs
            WHERE org_id = %s AND db_registry_id = %s
        """, (org_id, db_registry_id))
        row = cur.fetchone()
        return dict(row) if row else None


def list_assessment_configs(org_id: int) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT ac.*, d.name AS db_name, d.environment
            FROM assessment_configs ac
            JOIN db_registry d ON d.id = ac.db_registry_id
            WHERE ac.org_id = %s
            ORDER BY d.name
        """, (org_id,))
        return [dict(r) for r in cur.fetchall()]


# ─── Org-scoped registry helpers ─────────────────────────────────────────────

def list_db_registries_for_org(org_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        sql = "SELECT * FROM db_registry WHERE org_id = %s"
        if active_only:
            sql += " AND is_active = TRUE"
        sql += " ORDER BY environment, name"
        cur.execute(sql, (org_id,))
        return [dict(r) for r in cur.fetchall()]


def get_db_registry_for_org(org_id: int, name: str) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM db_registry WHERE org_id = %s AND name = %s",
            (org_id, name))
        row = cur.fetchone()
        return dict(row) if row else None


def get_db_summary_for_org(org_id: int) -> List[Dict[str, Any]]:
    """One row per database in the org with its latest run stats."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                d.id, d.name, d.environment, d.owner_label,
                d.last_run_at, d.last_health, d.is_active, d.tags,
                r.id             AS last_run_id,
                r.label          AS last_run_label,
                r.timestamp      AS last_run_ts,
                r.total_objects, r.total_issues,
                r.critical_count, r.high_count,
                r.medium_count,  r.low_count,
                r.health_score,  r.duration_sec,
                r.status         AS run_status
            FROM db_registry d
            LEFT JOIN LATERAL (
                SELECT * FROM runs
                 WHERE db_registry_id = d.id
                 ORDER BY timestamp DESC LIMIT 1
            ) r ON TRUE
            WHERE d.org_id = %s AND d.is_active = TRUE
            ORDER BY COALESCE(r.health_score, 0) ASC
        """, (org_id,))
        return [dict(r) for r in cur.fetchall()]


def list_runs_for_org(org_id: int, limit: int = 50,
                      db_registry_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        if db_registry_id is not None:
            cur.execute("""
                SELECT r.*, d.name AS db_name, d.environment AS db_env
                  FROM runs r
                  LEFT JOIN db_registry d ON d.id = r.db_registry_id
                 WHERE r.org_id = %s AND r.db_registry_id = %s
                 ORDER BY r.timestamp DESC LIMIT %s
            """, (org_id, db_registry_id, limit))
        else:
            cur.execute("""
                SELECT r.*, d.name AS db_name, d.environment AS db_env
                  FROM runs r
                  LEFT JOIN db_registry d ON d.id = r.db_registry_id
                 WHERE r.org_id = %s
                 ORDER BY r.timestamp DESC LIMIT %s
            """, (org_id, limit))
        return [dict(r) for r in cur.fetchall()]


# ─── Super-admin helpers ──────────────────────────────────────────────────────

def get_platform_stats() -> Dict[str, Any]:
    """Aggregate stats for super-admin portal."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM organizations WHERE is_active=TRUE)  AS orgs,
                (SELECT COUNT(*) FROM users         WHERE is_active=TRUE)  AS users,
                (SELECT COUNT(*) FROM db_registry   WHERE is_active=TRUE)  AS databases,
                (SELECT COUNT(*) FROM runs)                                  AS total_runs,
                (SELECT COUNT(*) FROM runs WHERE timestamp > NOW()-INTERVAL '30 days') AS runs_30d
        """)
        row = cur.fetchone()
        return dict(row) if row else {}
