"""
SQL Optimizer Routes - Phase 2
Ollama integration for optimization suggestions and UAT testing
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

from dbanalyser.db.connection import get_db
from dbanalyser.auth.rbac import require_auth
from dbanalyser.services.ollama_service import get_optimizer, check_ollama_health
from dbanalyser.services.optimization_db_utils import (
    execute_on_database,
    compare_query_results,
    sanitize_sql,
    estimate_query_complexity,
    extract_query_plan_metrics,
)

router = APIRouter(prefix="/optimizer", tags=["optimizer"])


@router.get("/health")
async def check_optimizer_health():
    """Check if Ollama is available and model is loaded"""
    try:
        health = await check_ollama_health()
        return {
            "ollama_available": health["available"],
            "models": health["models"],
            "model_loaded": health["model_loaded"],
            "recommended_model": "mistral" if health["model_loaded"] else "neural-chat",
            "setup_instructions": "Run: ollama pull mistral" if not health["model_loaded"] else None,
        }
    except Exception as e:
        return {
            "ollama_available": False,
            "error": str(e),
            "setup_instructions": "Ollama not running. Run: ollama serve",
        }


@router.post("/suggest")
async def get_optimization_suggestion(
    finding_id: Optional[int] = None,
    object_name: Optional[str] = None,
    sql_code: str = None,
    object_type: str = None,
    rule_id: str = None,
    issue_description: str = None,
    rule_recommendation: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """
    Get SQL optimization suggestion from Ollama

    Args:
        finding_id: Finding to optimize (loads SQL from database)
        object_name: Object name if not using finding_id
        sql_code: SQL code to optimize
        object_type: Type (Function, Procedure, View)
        rule_id: Rule that detected the issue
        issue_description: What's wrong
        rule_recommendation: Optional guidance from the rule

    Returns:
        {
            "optimization_id": "uuid",
            "suggested_sql": "optimized code",
            "confidence_score": 0.85,
            "estimated_improvement_pct": 35,
            "estimated_risk_level": "low",
            "response_time_ms": 8500,
            "model": "mistral",
            "error": null
        }
    """
    try:
        # Load SQL from finding if finding_id provided
        if finding_id:
            from dbanalyser.db.models import Finding

            finding = db.query(Finding).filter(Finding.id == finding_id).first()
            if not finding:
                raise HTTPException(status_code=404, detail="Finding not found")

            sql_code = sql_code or finding.issue  # Fallback to issue text
            object_type = object_type or finding.object_type
            rule_id = rule_id or finding.rule_id
            issue_description = issue_description or finding.issue
            object_name = object_name or finding.object_name

        if not sql_code or not rule_id:
            raise HTTPException(
                status_code=400,
                detail="sql_code and rule_id are required",
            )

        # Estimate complexity before calling Ollama
        complexity = estimate_query_complexity(sql_code)

        # Get optimizer and request suggestion
        optimizer = await get_optimizer()
        result = await optimizer.optimize_sql(
            sql_code=sql_code,
            object_type=object_type or "Unknown",
            rule_id=rule_id,
            issue_description=issue_description or "Performance optimization needed",
            rule_recommendation=rule_recommendation,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Ollama error: {result['error']}",
            )

        # Store optimization suggestion in database
        from dbanalyser.db.models import SchemaObjectOptimization

        optimization = SchemaObjectOptimization(
            finding_id=finding_id,
            object_name=object_name,
            object_type=object_type,
            original_sql=sql_code,
            suggested_sql=result["suggested_sql"],
            confidence_score=result["confidence_score"],
            estimated_improvement_pct=result["estimated_improvement_pct"],
            estimated_risk_level=result["estimated_risk_level"],
            ollama_model=result["model"],
            ollama_response_time_ms=result["response_time_ms"],
            explanation=result["explanation"],
            created_at=datetime.utcnow(),
            created_by_user_id=current_user.id,
            status="suggested",
        )

        db.add(optimization)
        db.commit()
        db.refresh(optimization)

        return {
            "optimization_id": optimization.id,
            "finding_id": finding_id,
            "suggested_sql": result["suggested_sql"],
            "explanation": result["explanation"],
            "confidence_score": result["confidence_score"],
            "estimated_improvement_pct": result["estimated_improvement_pct"],
            "estimated_risk_level": result["estimated_risk_level"],
            "response_time_ms": result["response_time_ms"],
            "model": result["model"],
            "query_complexity": complexity,
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_optimization(
    optimization_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """
    Test optimization on UAT database

    Executes both original and optimized SQL, compares results

    Returns:
        {
            "attempt_id": 123,
            "success": true,
            "original_time_ms": 1250.45,
            "optimized_time_ms": 450.20,
            "improvement_pct": 64.0,
            "data_integrity_ok": true,
            "metrics": [
                { "metric": "execution_time", "original": 1250, "optimized": 450, "unit": "ms" },
                { "metric": "row_count", "original": 5000, "optimized": 5000, "unit": "rows" }
            ],
            "error": null
        }
    """
    try:
        from dbanalyser.db.models import (
            SchemaObjectOptimization,
            OptimizationAttempt,
            OptimizationMetric,
        )

        # Get optimization
        optimization = (
            db.query(SchemaObjectOptimization)
            .filter(SchemaObjectOptimization.id == optimization_id)
            .first()
        )
        if not optimization:
            raise HTTPException(status_code=404, detail="Optimization not found")

        # Sanitize SQL
        original_sql = sanitize_sql(optimization.original_sql)
        suggested_sql = sanitize_sql(optimization.suggested_sql)

        # Execute both on UAT database
        original_result = await execute_on_database(
            original_sql, db, explain_plan=True
        )
        optimized_result = await execute_on_database(
            suggested_sql, db, explain_plan=True
        )

        # Compare results
        comparison = compare_query_results(original_result, optimized_result)

        # Create attempt record
        attempt_number = (
            db.query(OptimizationAttempt)
            .filter(OptimizationAttempt.optimization_id == optimization_id)
            .count()
            + 1
        )

        attempt = OptimizationAttempt(
            optimization_id=optimization_id,
            attempt_number=attempt_number,
            test_database="UAT",
            test_date=datetime.utcnow(),
            status="success" if comparison["data_integrity_ok"] else "failed",
            original_execution_ms=comparison["original_time_ms"],
            optimized_execution_ms=comparison["optimized_time_ms"],
            improvement_pct=comparison["improvement_pct"],
            original_row_count=comparison["original_rows"],
            optimized_row_count=comparison["optimized_rows"],
            data_integrity_verified=1
            if comparison["data_integrity_ok"]
            else 0,
            error_message=comparison["error"],
            created_by_user_id=current_user.id,
        )

        db.add(attempt)
        db.flush()

        # Store metrics
        metrics_data = [
            ("execution_time_original", str(comparison["original_time_ms"]), "ms", "lower_better"),
            ("execution_time_optimized", str(comparison["optimized_time_ms"]), "ms", "lower_better"),
            ("improvement_percent", str(comparison["improvement_pct"]), "%", "higher_better"),
            ("row_count_original", str(comparison["original_rows"]), "rows", "same"),
            ("row_count_optimized", str(comparison["optimized_rows"]), "rows", "same"),
            ("is_faster", "yes" if comparison["is_faster"] else "no", "boolean", "higher_better"),
        ]

        for metric_name, value, unit, direction in metrics_data:
            metric = OptimizationMetric(
                attempt_id=attempt.id,
                metric_name=metric_name,
                original_value=None,
                optimized_value=value,
                unit=unit,
                improvement_direction=direction,
            )
            db.add(metric)

        # Update optimization status
        optimization.status = "tested"
        db.commit()
        db.refresh(attempt)

        return {
            "attempt_id": attempt.id,
            "optimization_id": optimization_id,
            "attempt_number": attempt_number,
            "success": comparison["data_integrity_ok"],
            "original_time_ms": comparison["original_time_ms"],
            "optimized_time_ms": comparison["optimized_time_ms"],
            "improvement_pct": comparison["improvement_pct"],
            "is_faster": comparison["is_faster"],
            "data_integrity_ok": comparison["data_integrity_ok"],
            "metrics": [
                {
                    "metric": "Execution Time Original",
                    "value": comparison["original_time_ms"],
                    "unit": "ms",
                },
                {
                    "metric": "Execution Time Optimized",
                    "value": comparison["optimized_time_ms"],
                    "unit": "ms",
                },
                {
                    "metric": "Improvement",
                    "value": comparison["improvement_pct"],
                    "unit": "%",
                },
                {
                    "metric": "Row Count Match",
                    "value": comparison["row_count_matches"],
                    "unit": "boolean",
                },
            ],
            "error": comparison["error"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{finding_id}")
async def get_optimization_history(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Get all optimization attempts for a finding"""
    try:
        from dbanalyser.db.models import SchemaObjectOptimization, OptimizationAttempt

        optimizations = (
            db.query(SchemaObjectOptimization)
            .filter(SchemaObjectOptimization.finding_id == finding_id)
            .all()
        )

        history = []
        for opt in optimizations:
            attempts = (
                db.query(OptimizationAttempt)
                .filter(OptimizationAttempt.optimization_id == opt.id)
                .order_by(OptimizationAttempt.attempt_number)
                .all()
            )

            history.append(
                {
                    "optimization_id": opt.id,
                    "status": opt.status,
                    "confidence_score": opt.confidence_score,
                    "estimated_improvement_pct": opt.estimated_improvement_pct,
                    "estimated_risk_level": opt.estimated_risk_level,
                    "created_at": opt.created_at.isoformat() if opt.created_at else None,
                    "attempts": [
                        {
                            "attempt_number": a.attempt_number,
                            "test_date": a.test_date.isoformat() if a.test_date else None,
                            "status": a.status,
                            "improvement_pct": a.improvement_pct,
                            "execution_time_ms": a.original_execution_ms,
                            "data_integrity_ok": bool(a.data_integrity_verified),
                        }
                        for a in attempts
                    ],
                }
            )

        return {
            "finding_id": finding_id,
            "total_suggestions": len(optimizations),
            "history": history,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download/{optimization_id}")
async def download_optimization(
    optimization_id: int,
    include_comparison: bool = True,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """
    Prepare optimization for download as SQL file

    Returns SQL content that can be downloaded
    """
    try:
        from dbanalyser.db.models import SchemaObjectOptimization

        optimization = (
            db.query(SchemaObjectOptimization)
            .filter(SchemaObjectOptimization.id == optimization_id)
            .first()
        )
        if not optimization:
            raise HTTPException(status_code=404, detail="Optimization not found")

        # Build SQL file content
        content = "-- SQL Optimization Generated by DBAnalyser Phase 2\n"
        content += f"-- Generated: {datetime.utcnow().isoformat()}\n"
        content += f"-- Confidence: {optimization.confidence_score * 100:.0f}%\n"
        content += f"-- Estimated Improvement: {optimization.estimated_improvement_pct}%\n"
        content += f"-- Risk Level: {optimization.estimated_risk_level}\n"
        content += f"-- Explanation: {optimization.explanation}\n\n"

        if include_comparison:
            content += "-- ORIGINAL SQL:\n"
            content += "/*\n"
            content += optimization.original_sql
            content += "\n*/\n\n"

        content += "-- OPTIMIZED SQL:\n"
        content += optimization.suggested_sql
        content += "\n"

        # Increment download count
        optimization.download_count = (optimization.download_count or 0) + 1
        db.commit()

        return {
            "filename": f"optimization_{optimization_id}.sql",
            "content": content,
            "size_bytes": len(content),
            "ready_for_download": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit-cr/{optimization_id}")
async def submit_change_request(
    optimization_id: int,
    cr_title: str,
    cr_description: str,
    implementation_notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """
    Submit optimization as a change request

    Creates a CR record linked to the optimization
    """
    try:
        from dbanalyser.db.models import (
            SchemaObjectOptimization,
            OptimizationChangeRequest,
        )

        optimization = (
            db.query(SchemaObjectOptimization)
            .filter(SchemaObjectOptimization.id == optimization_id)
            .first()
        )
        if not optimization:
            raise HTTPException(status_code=404, detail="Optimization not found")

        # Create CR record
        cr = OptimizationChangeRequest(
            optimization_id=optimization_id,
            cr_title=cr_title,
            cr_description=cr_description,
            implementation_notes=implementation_notes,
            submitted_date=datetime.utcnow(),
            submitted_by_user_id=current_user.id,
            status="submitted",
        )

        optimization.status = "cr_submitted"
        db.add(cr)
        db.commit()
        db.refresh(cr)

        return {
            "cr_id": cr.id,
            "optimization_id": optimization_id,
            "status": "submitted",
            "message": "Change request submitted successfully",
            "next_steps": "CR will be reviewed by team lead",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def list_suggestions(
    run_id: Optional[int] = None,
    status: Optional[str] = Query(None, regex="suggested|tested|approved|cr_submitted"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Get paginated list of optimization suggestions"""
    try:
        from dbanalyser.db.models import SchemaObjectOptimization, Finding

        query = db.query(SchemaObjectOptimization)

        if run_id:
            query = query.join(Finding).filter(Finding.run_id == run_id)

        if status:
            query = query.filter(SchemaObjectOptimization.status == status)

        total = query.count()
        suggestions = query.limit(limit).offset(offset).all()

        return {
            "data": [
                {
                    "id": s.id,
                    "finding_id": s.finding_id,
                    "object_name": s.object_name,
                    "status": s.status,
                    "confidence_score": s.confidence_score,
                    "estimated_improvement_pct": s.estimated_improvement_pct,
                    "estimated_risk_level": s.estimated_risk_level,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in suggestions
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
