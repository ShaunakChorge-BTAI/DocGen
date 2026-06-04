"""
Phase 5: Assessment Wizard API Routes
Multi-step wizard, scan execution, results, comparisons, and recommendations
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict

from database import get_db
from services.assessment_wizard_service import AssessmentWizardService
from services.recommendations_engine import RecommendationsEngine
from schemas import (
    DatabaseSelectionInput,
    AssessmentConfigInput,
    ComparisonInput,
    ScanProgressUpdate
)

router = APIRouter(prefix="/api/v1", tags=["phase5"])


# ============================================================================
# PHASE 5: Assessment Wizard Session Endpoints
# ============================================================================

@router.post("/wizard/start")
async def start_assessment_wizard(
    user_id: int = Query(...),
    template_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Start a new assessment wizard session"""
    service = AssessmentWizardService(db)
    try:
        result = service.start_assessment_session(user_id, template_id)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wizard/session/{session_token}")
async def get_wizard_session_state(
    session_token: str,
    db: Session = Depends(get_db)
):
    """Get current state of wizard session"""
    service = AssessmentWizardService(db)
    try:
        session = service.get_session_state(session_token)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "data": session}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# PHASE 5: Wizard Step Endpoints
# ============================================================================

@router.post("/wizard/select-databases")
async def select_databases(
    session_token: str = Query(...),
    database_ids: List[int] = Query(...),
    db: Session = Depends(get_db)
):
    """Select databases for assessment (Step 1 -> 2)"""
    service = AssessmentWizardService(db)
    try:
        result = service.select_databases(session_token, database_ids)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/wizard/configure")
async def configure_assessment(
    session_token: str = Query(...),
    config: Dict = Body(...),
    db: Session = Depends(get_db)
):
    """Configure assessment parameters (Step 2 -> 3)"""
    service = AssessmentWizardService(db)
    try:
        result = service.configure_assessment(
            session_token,
            config
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/wizard/start-scan")
async def start_scan(
    session_token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Begin assessment scan (Step 3 -> 4)"""
    service = AssessmentWizardService(db)
    try:
        result = service.start_scan(session_token)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/wizard/cancel")
async def cancel_assessment(
    session_token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Cancel an ongoing assessment"""
    service = AssessmentWizardService(db)
    try:
        result = service.cancel_assessment(session_token)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# PHASE 5: Scan Progress & Results Endpoints
# ============================================================================

@router.get("/wizard/progress/{session_token}")
async def get_scan_progress(
    session_token: str,
    db: Session = Depends(get_db)
):
    """Get current scan progress"""
    service = AssessmentWizardService(db)
    try:
        progress = service.get_scan_progress(session_token)
        return {"success": True, "data": progress}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/wizard/progress/update")
async def update_scan_progress(
    session_token: str = Query(...),
    progress: int = Query(..., ge=0, le=100),
    db: Session = Depends(get_db)
):
    """Update scan progress (internal use)"""
    service = AssessmentWizardService(db)
    try:
        result = service.update_scan_progress(session_token, progress)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wizard/results/{session_token}")
async def get_assessment_results(
    session_token: str,
    db: Session = Depends(get_db)
):
    """Get assessment results"""
    service = AssessmentWizardService(db)
    try:
        results = service.get_assessment_results(session_token)
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# PHASE 5: Comparison & Trend Endpoints
# ============================================================================

@router.post("/wizard/compare")
async def compare_assessments(
    comparison: ComparisonInput,
    db: Session = Depends(get_db)
):
    """Compare current vs baseline assessment"""
    service = RecommendationsEngine(db)
    try:
        result = service.compare_assessments(
            comparison.database_id,
            comparison.baseline_run_id,
            comparison.current_run_id
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wizard/trends/{database_id}")
async def get_assessment_trend(
    database_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get assessment trends for a database"""
    service = RecommendationsEngine(db)
    try:
        trends = service.get_assessment_trend(database_id, days)
        return {"success": True, "data": trends}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# PHASE 5: Recommendations Endpoints
# ============================================================================

@router.post("/wizard/recommendations/{assessment_run_id}")
async def generate_recommendations(
    assessment_run_id: int,
    max_recommendations: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Generate recommendations from assessment results"""
    service = RecommendationsEngine(db)
    try:
        recommendations = service.generate_recommendations(
            assessment_run_id,
            max_recommendations
        )
        return {"success": True, "data": recommendations}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wizard/quick-wins/{assessment_run_id}")
async def get_quick_wins(
    assessment_run_id: int,
    db: Session = Depends(get_db)
):
    """Get quick wins: low effort, high impact recommendations"""
    service = RecommendationsEngine(db)
    try:
        quick_wins = service.get_quick_wins(assessment_run_id)
        return {"success": True, "data": quick_wins}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wizard/recommendations/{rec_type}")
async def get_recommendations_by_type(
    rec_type: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get recommendations filtered by type"""
    service = RecommendationsEngine(db)
    try:
        recommendations = service.get_recommendations_by_priority(rec_type, limit)
        return {"success": True, "data": recommendations}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# PHASE 5: Assessment History Endpoints
# ============================================================================

@router.get("/wizard/history/{user_id}")
async def get_assessment_history(
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get past assessments for a user"""
    service = AssessmentWizardService(db)
    try:
        history = service.get_assessment_history(user_id, limit)
        return {"success": True, "data": history}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
