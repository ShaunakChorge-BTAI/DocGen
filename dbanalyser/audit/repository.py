"""
Audit Repository
================
Query helpers for reading audit_logs from PostgreSQL.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """One row from audit_logs."""
    id:            int
    username:      str
    action:        str
    resource_type: str
    resource_id:   str
    details:       Dict[str, Any]
    ip_address:    str
    created_at:    datetime


def get_audit_logs(
    username:      Optional[str] = None,
    action:        Optional[str] = None,
    resource_type: Optional[str] = None,
    limit:         int = 100,
    offset:        int = 0,
) -> List[AuditEntry]:
    """
    Fetch audit log entries, optionally filtered.

    Args:
        username      : filter by username (exact match)
        action        : filter by action (exact match)
        resource_type : filter by resource type
        limit         : max rows to return
        offset        : skip this many rows (for pagination)

    Returns:
        List of AuditEntry objects sorted by created_at DESC.
    """
    try:
        from dbanalyser.db.connection import get_cursor
        wheres: List[str] = []
        params: list      = []

        if username:
            wheres.append("username = %s"); params.append(username)
        if action:
            wheres.append("action = %s"); params.append(action)
        if resource_type:
            wheres.append("resource_type = %s"); params.append(resource_type)

        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        params += [limit, offset]

        with get_cursor() as cur:
            cur.execute(f"""
                SELECT id, username, action, resource_type, resource_id,
                       details, ip_address, created_at
                FROM audit_logs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params)
            rows = cur.fetchall() or []
            entries = []
            for r in rows:
                entries.append(AuditEntry(
                    id=r["id"],
                    username=r["username"],
                    action=r["action"],
                    resource_type=r["resource_type"] or "",
                    resource_id=r["resource_id"] or "",
                    details=r["details"] or {},
                    ip_address=r["ip_address"] or "",
                    created_at=r["created_at"],
                ))
            return entries
    except Exception as exc:
        log.warning("get_audit_logs failed: %s", exc)
        return []


def count_audit_logs(
    username:      Optional[str] = None,
    action:        Optional[str] = None,
    resource_type: Optional[str] = None,
) -> int:
    """Return total count of audit log entries matching the filters."""
    try:
        from dbanalyser.db.connection import get_cursor
        wheres: List[str] = []
        params: list      = []
        if username:
            wheres.append("username = %s"); params.append(username)
        if action:
            wheres.append("action = %s"); params.append(action)
        if resource_type:
            wheres.append("resource_type = %s"); params.append(resource_type)
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        with get_cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM audit_logs {where_sql}", params)
            row = cur.fetchone()
            return int(row["cnt"]) if row else 0
    except Exception as exc:
        log.warning("count_audit_logs failed: %s", exc)
        return 0
