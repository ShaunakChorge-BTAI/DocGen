"""
Audit Logger
============
Records every significant user action to the audit_logs PostgreSQL table.

Usage::

    from dbanalyser.audit import log_action
    log_action("alice", "optimize", "stored_procedure", "usp_Process",
               details={"model": "claude-3-5-haiku"})
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


def log_action(
    username:      str,
    action:        str,
    resource_type: str = "",
    resource_id:   str = "",
    details:       Optional[Dict[str, Any]] = None,
    ip_address:    str = "",
) -> bool:
    """
    Write one audit record to the audit_logs table.

    Args:
        username      : who performed the action
        action        : verb, e.g. "optimize", "ingest", "login", "run_scan"
        resource_type : e.g. "stored_procedure", "database", "finding"
        resource_id   : e.g. object name, DB name, finding ID
        details       : arbitrary JSON-serialisable dict for extra context
        ip_address    : caller's IP address (optional)

    Returns:
        True on success, False on failure (never raises).
    """
    details_json = json.dumps(details or {}, default=str)
    try:
        from dbanalyser.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO audit_logs
                    (username, action, resource_type, resource_id,
                     details, ip_address)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            """, (
                username or "system",
                action,
                resource_type,
                resource_id,
                details_json,
                ip_address,
            ))
        return True
    except Exception as exc:
        log.warning("audit log_action failed: %s", exc)
        return False
