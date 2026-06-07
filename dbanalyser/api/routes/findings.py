"""Findings Management Routes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from dbanalyser.api.auth import AuthDep
from dbanalyser.api.schemas import FindingListResponse
from dbanalyser.db.connection import get_cursor
from dbanalyser.db.repository import get_findings, get_finding_by_id

router = APIRouter(prefix="/findings", tags=["Findings"])


@router.get("/", response_model=FindingListResponse, dependencies=[AuthDep])
def list_findings(
    run_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=5000),
):
    """List findings with optional filters."""
    if run_id is None:
        raise HTTPException(status_code=400, detail="run_id is required")
    try:
        rows = get_findings(
            run_int_id=run_id,
            severity=severity,
            category=category,
            status=status,
            limit=limit,
        )
        if hasattr(rows, "to_dict"):
            rows = rows.to_dict("records")
        return FindingListResponse(findings=rows, total=len(rows), run_id=run_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary/{run_id}", dependencies=[AuthDep])
def findings_summary(run_id: int) -> Dict[str, Any]:
    """Quick severity breakdown for a run."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM findings WHERE run_id = %s",
                (run_id,),
            )
            total = cur.fetchone()["total"]

            cur.execute(
                """
                SELECT severity, COUNT(*) AS count
                  FROM findings
                 WHERE run_id = %s
                 GROUP BY severity
                 ORDER BY severity
                """,
                (run_id,),
            )
            severity_counts = {row["severity"]: row["count"] for row in cur.fetchall()}

        return {
            "run_id": run_id,
            "total_findings": total,
            "severity_counts": severity_counts,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/{finding_id}", dependencies=[AuthDep])
def get_finding_detail(finding_id: int):
    """Get single finding by ID."""
    try:
        finding = get_finding_by_id(finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")
        # Ensure we return a structured payload matching the frontend's expectations
        return finding
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.patch("/{finding_id}/status", dependencies=[AuthDep])
def patch_finding_status(finding_id: int, body: dict):
    """Update finding status and record history."""
    try:
        from dbanalyser.db.repository import update_finding_status
        from dbanalyser.db.connection import get_cursor
        new_status = body.get("new_status")
        reason = body.get("reason", "")
        if new_status:
            # Get old status first for history
            with get_cursor() as cur:
                cur.execute("SELECT status FROM findings WHERE id = %s", (finding_id,))
                row = cur.fetchone()
                old_status = row["status"] if row else None
            update_finding_status(finding_id, new_status)
            # Record status history
            try:
                with get_cursor() as cur:
                    cur.execute(
                        """INSERT INTO finding_status_history
                           (finding_id, old_status, new_status, reason, changed_at)
                           VALUES (%s, %s, %s, %s, NOW())
                           ON CONFLICT DO NOTHING""",
                        (finding_id, old_status, new_status, reason)
                    )
            except Exception:
                pass  # Table may not exist yet
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/{finding_id}/comments", dependencies=[AuthDep])
def post_finding_comment(finding_id: int, body: dict):
    """Add a comment to a finding."""
    try:
        from dbanalyser.db.connection import get_cursor
        comment_text = body.get("comment_text", "")
        is_internal = body.get("is_internal", False)
        if not comment_text.strip():
            raise HTTPException(status_code=400, detail="comment_text is required")
        with get_cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO finding_comments (finding_id, comment_text, is_internal, created_at)
                       VALUES (%s, %s, %s, NOW()) RETURNING id""",
                    (finding_id, comment_text, is_internal)
                )
            except Exception:
                # Table may not exist — create it on the fly
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS finding_comments (
                        id SERIAL PRIMARY KEY,
                        finding_id INTEGER NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
                        user_id INTEGER,
                        comment_text TEXT NOT NULL,
                        is_internal BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute(
                    """INSERT INTO finding_comments (finding_id, comment_text, is_internal, created_at)
                       VALUES (%s, %s, %s, NOW()) RETURNING id""",
                    (finding_id, comment_text, is_internal)
                )
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

