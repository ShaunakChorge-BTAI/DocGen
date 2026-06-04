"""REST routes — /audit  (audit log queries)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from dbanalyser.api.auth    import AuthDep
from dbanalyser.api.schemas import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit"])


def _to_response(entry) -> AuditLogResponse:
    """Convert AuditEntry dataclass (or dict) to response model."""
    if isinstance(entry, dict):
        return AuditLogResponse(
            id            = entry["id"],
            username      = entry.get("username", ""),
            action        = entry.get("action", ""),
            resource_type = entry.get("resource_type", ""),
            resource_id   = entry.get("resource_id", ""),
            details       = entry.get("details") or {},
            ip_address    = entry.get("ip_address", ""),
            created_at    = entry.get("created_at"),
        )
    return AuditLogResponse(
        id            = entry.id,
        username      = entry.username,
        action        = entry.action,
        resource_type = entry.resource_type,
        resource_id   = entry.resource_id,
        details       = entry.details or {},
        ip_address    = entry.ip_address,
        created_at    = entry.created_at,
    )


@router.get("/", response_model=AuditLogListResponse, dependencies=[AuthDep])
def list_audit_logs(
    username:      Optional[str] = Query(None, description="Filter by username"),
    action:        Optional[str] = Query(None, description="Filter by action verb"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit:         int           = Query(100, ge=1, le=1000),
    offset:        int           = Query(0, ge=0),
):
    """
    Return paginated audit log entries, newest first.

    Use the `username`, `action`, and `resource_type` query params to filter.
    """
    from dbanalyser.audit.repository import get_audit_logs, count_audit_logs

    entries = get_audit_logs(username=username, action=action,
                             resource_type=resource_type,
                             limit=limit, offset=offset)
    total = count_audit_logs(username=username, action=action,
                             resource_type=resource_type)
    return AuditLogListResponse(
        logs   = [_to_response(e) for e in entries],
        total  = total,
        limit  = limit,
        offset = offset,
    )
