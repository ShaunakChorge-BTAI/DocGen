"""
Findings Management Routes - Phase 1
Status tracking, detailed views, comments, history
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from dbanalyser.db.connection import get_db
from dbanalyser.auth.rbac import require_auth

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("/")
async def list_findings(
    run_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    rule_id: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """List findings with pagination and filtering"""
    try:
        from dbanalyser.db.models import Finding

        query = db.query(Finding)

        if run_id:
            query = query.filter(Finding.run_id == run_id)
        if severity:
            query = query.filter(Finding.severity == severity)
        if status:
            query = query.filter(Finding.status == status)
        if rule_id:
            query = query.filter(Finding.rule_id == rule_id)
        if assigned_to == "me":
            query = query.filter(Finding.assigned_to_user_id == current_user.id)
        elif assigned_to:
            query = query.filter(Finding.assigned_to_user_id == int(assigned_to))

        total = query.count()

        findings = (
            query.order_by(desc(Finding.severity), desc(Finding.created_at))
            .limit(limit)
            .offset(offset)
            .all()
        )

        return {
            "data": [
                {
                    "id": f.id,
                    "run_id": f.run_id,
                    "rule_id": f.rule_id,
                    "object_name": f.object_name,
                    "object_type": f.object_type,
                    "severity": f.severity,
                    "issue": f.issue,
                    "recommendation": f.recommendation,
                    "status": f.status,
                    "assigned_to_user_id": f.assigned_to_user_id,
                    "priority": f.priority,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in findings
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "page": (offset // limit) + 1,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{finding_id}")
async def get_finding_detail(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Get full finding details"""
    try:
        from dbanalyser.db.models import (
            Finding,
            SchemaObject,
            FindingStatusHistory,
            FindingComment,
        )

        finding = db.query(Finding).filter(Finding.id == finding_id).first()
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

        schema_object = None
        if finding.object_name:
            schema_object = (
                db.query(SchemaObject)
                .filter(SchemaObject.object_name == finding.object_name)
                .first()
            )

        status_history = (
            db.query(FindingStatusHistory)
            .filter(FindingStatusHistory.finding_id == finding_id)
            .order_by(FindingStatusHistory.changed_at)
            .all()
        )

        comments = (
            db.query(FindingComment)
            .filter(FindingComment.finding_id == finding_id)
            .order_by(FindingComment.created_at)
            .all()
        )

        return {
            "finding": {
                "id": finding.id,
                "run_id": finding.run_id,
                "rule_id": finding.rule_id,
                "object_name": finding.object_name,
                "object_type": finding.object_type,
                "severity": finding.severity,
                "issue": finding.issue,
                "recommendation": finding.recommendation,
                "status": finding.status,
                "assigned_to_user_id": finding.assigned_to_user_id,
                "priority": finding.priority,
                "created_at": finding.created_at.isoformat() if finding.created_at else None,
            },
            "schema_object": {
                "name": schema_object.object_name,
                "type": schema_object.object_type,
                "definition": schema_object.current_definition,
                "size_bytes": schema_object.definition_size_bytes,
            } if schema_object else None,
            "status_history": [
                {
                    "old_status": h.old_status,
                    "new_status": h.new_status,
                    "changed_at": h.changed_at.isoformat() if h.changed_at else None,
                    "reason": h.reason,
                }
                for h in status_history
            ],
            "comments": [
                {
                    "id": c.id,
                    "user_id": c.user_id,
                    "comment_text": c.comment_text,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in comments
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{finding_id}/status")
async def update_finding_status(
    finding_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Update finding status"""
    try:
        from dbanalyser.db.models import Finding, FindingStatusHistory

        finding = db.query(Finding).filter(Finding.id == finding_id).first()
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

        new_status = body.get("new_status")
        reason = body.get("reason")

        valid_statuses = [
            "Pending", "In Progress", "Optimized", "Reviewed",
            "CR_Submitted", "CR_Approved", "Ready_to_Deploy", "Acknowledged",
        ]
        if new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail="Invalid status")

        old_status = finding.status
        finding.status = new_status
        finding.status_updated_at = datetime.utcnow()
        finding.status_updated_by_user_id = current_user.id
        finding.status_notes = reason

        history = FindingStatusHistory(
            finding_id=finding_id,
            old_status=old_status,
            new_status=new_status,
            changed_by_user_id=current_user.id,
            reason=reason,
            changed_at=datetime.utcnow(),
        )

        db.add(history)
        db.commit()
        db.refresh(finding)

        return {"status": "updated", "finding": {"id": finding.id, "status": finding.status}}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{finding_id}/comments")
async def add_comment(
    finding_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Add comment to finding"""
    try:
        from dbanalyser.db.models import Finding, FindingComment

        finding = db.query(Finding).filter(Finding.id == finding_id).first()
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

        comment = FindingComment(
            finding_id=finding_id,
            user_id=current_user.id,
            comment_text=body.get("comment_text"),
            is_internal=body.get("is_internal", False),
            created_at=datetime.utcnow(),
        )

        db.add(comment)
        db.commit()
        db.refresh(comment)

        return {
            "id": comment.id,
            "comment_text": comment.comment_text,
            "created_at": comment.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{finding_id}/history")
async def get_finding_history(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Get status change history"""
    try:
        from dbanalyser.db.models import Finding, FindingStatusHistory

        finding = db.query(Finding).filter(Finding.id == finding_id).first()
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

        history = (
            db.query(FindingStatusHistory)
            .filter(FindingStatusHistory.finding_id == finding_id)
            .order_by(FindingStatusHistory.changed_at)
            .all()
        )

        return {
            "finding_id": finding_id,
            "current_status": finding.status,
            "history": [
                {
                    "version": idx + 1,
                    "old_status": h.old_status,
                    "new_status": h.new_status,
                    "changed_at": h.changed_at.isoformat() if h.changed_at else None,
                    "reason": h.reason,
                }
                for idx, h in enumerate(history)
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
