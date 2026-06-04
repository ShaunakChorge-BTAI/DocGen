"""
Phase 4: Database Management & CR Workflow API Routes
Change requests, approvals, deployments, and rollback management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from services.change_request_service import ChangeRequestService
from services.deployment_service import DeploymentService
from schemas import (
    ChangeRequestCreate,
    ApprovalInput,
    DeploymentInput,
    RollbackInput
)

router = APIRouter(prefix="/api/v1", tags=["phase4"])


# ============================================================================
# PHASE 4: Change Request Workflow Endpoints
# ============================================================================

@router.post("/change-requests")
async def create_change_request(
    cr: ChangeRequestCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Create a new change request"""
    service = ChangeRequestService(db)
    try:
        result = service.create_change_request(
            finding_id=cr.finding_id,
            title=cr.title,
            description=cr.description,
            priority=cr.priority,
            user_id=user_id
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/change-requests/{cr_id}/submit")
async def submit_change_request(
    cr_id: str,
    db: Session = Depends(get_db)
):
    """Submit CR for approval workflow"""
    service = ChangeRequestService(db)
    try:
        result = service.submit_change_request(cr_id)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/change-requests/{cr_id}")
async def get_change_request_details(
    cr_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a CR"""
    service = ChangeRequestService(db)
    try:
        cr = service.get_cr_details(cr_id)
        if not cr:
            raise HTTPException(status_code=404, detail="CR not found")
        return {"success": True, "data": cr}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/change-requests/{cr_id}/approvals")
async def get_approval_stages(
    cr_id: str,
    db: Session = Depends(get_db)
):
    """Get approval stages for a CR"""
    service = ChangeRequestService(db)
    try:
        stages = service.get_cr_approval_stages(cr_id)
        return {"success": True, "data": stages}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/change-requests/{cr_id}/approve/{stage}")
async def approve_change_request(
    cr_id: str,
    stage: int,
    approval: ApprovalInput,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Approve CR at a specific stage"""
    service = ChangeRequestService(db)
    try:
        result = service.approve_at_stage(
            cr_id=cr_id,
            stage=stage,
            user_id=user_id,
            comment=approval.comment
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/change-requests/{cr_id}/reject/{stage}")
async def reject_change_request(
    cr_id: str,
    stage: int,
    reason: str = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Reject CR at a specific stage"""
    service = ChangeRequestService(db)
    try:
        result = service.reject_change_request(
            cr_id=cr_id,
            stage=stage,
            user_id=user_id,
            reason=reason
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/approvals/pending")
async def get_pending_approvals(
    user_id: int = Query(...),
    role: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get pending CRs awaiting user's approval"""
    service = ChangeRequestService(db)
    try:
        crs = service.list_pending_approvals(user_id, role)
        return {"success": True, "data": crs}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/change-requests/status/{status}")
async def get_crs_by_status(
    status: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get CRs filtered by status"""
    service = ChangeRequestService(db)
    try:
        crs = service.get_cr_by_status(status, limit)
        return {"success": True, "data": crs}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# PHASE 4: Pre-Deployment & Deployment Endpoints
# ============================================================================

@router.post("/deployments/{cr_id}/pre-checks")
async def run_pre_deployment_checks(
    cr_id: str,
    db: Session = Depends(get_db)
):
    """Run pre-deployment validation checks"""
    service = DeploymentService(db)
    try:
        result = service.run_pre_deployment_checks(cr_id)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deployments")
async def deploy_change_request(
    deployment: DeploymentInput,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Deploy CR to target environment"""
    service = DeploymentService(db)
    try:
        result = service.deploy_to_environment(
            cr_id=deployment.cr_id,
            environment=deployment.environment,
            user_id=user_id
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deployments/{deployment_id}/validate")
async def run_post_deployment_validation(
    deployment_id: int,
    db: Session = Depends(get_db)
):
    """Run post-deployment validation tests"""
    service = DeploymentService(db)
    try:
        result = service.run_post_deployment_validation(deployment_id)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deployments/{cr_id}/audit-trail")
async def get_deployment_audit_trail(
    cr_id: str,
    db: Session = Depends(get_db)
):
    """Get audit trail for a deployment"""
    service = DeploymentService(db)
    try:
        audit_trail = service.get_deployment_audit_trail(cr_id)
        return {"success": True, "data": audit_trail}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deployments/{deployment_id}/can-rollback")
async def check_rollback_availability(
    deployment_id: int,
    db: Session = Depends(get_db)
):
    """Check if rollback is available for a deployment"""
    service = DeploymentService(db)
    try:
        can_rollback = service.can_rollback(deployment_id)
        return {"success": True, "data": {"can_rollback": can_rollback}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# PHASE 4: Rollback Endpoints
# ============================================================================

@router.post("/deployments/{deployment_id}/rollback")
async def execute_rollback(
    deployment_id: int,
    rollback: RollbackInput,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Execute rollback of a deployment"""
    service = DeploymentService(db)
    try:
        result = service.execute_rollback(
            deployment_id=deployment_id,
            user_id=user_id,
            reason=rollback.reason
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deployments/cr/{cr_id}/history")
async def get_deployment_history(
    cr_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get deployment history for a CR"""
    service = DeploymentService(db)
    try:
        history = service.get_deployment_history(cr_id, limit)
        return {"success": True, "data": history}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# PHASE 4: Database Version Management Endpoints
# ============================================================================

@router.post("/database-versions")
async def create_database_version(
    db_registry_id: int = Query(...),
    patch_notes: str = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Create a database version record"""
    service = DeploymentService(db)
    try:
        result = service.create_database_version(
            db_registry_id=db_registry_id,
            user_id=user_id,
            patch_notes=patch_notes
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
