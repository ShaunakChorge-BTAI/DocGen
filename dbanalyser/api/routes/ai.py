"""REST routes — /ai  (AI optimizer endpoints)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from dbanalyser.api.auth    import AuthDep
from dbanalyser.api.schemas import (
    AiOptimizationListResponse, AiOptimizationResponse,
    OptimizeRequest, OptimizeResponse,
    OptimizationChangeItem,
)

router = APIRouter(prefix="/ai", tags=["AI Optimizer"])


def _to_optimization_response(r: dict) -> AiOptimizationResponse:
    return AiOptimizationResponse(
        id             = r["id"],
        run_id         = r.get("run_id"),
        db_registry_id = r.get("db_registry_id"),
        object_name    = r.get("object_name", ""),
        original_sql   = r.get("original_sql"),
        optimized_sql  = r.get("optimized_sql"),
        reasoning      = r.get("reasoning"),
        confidence_score = float(r.get("confidence_score", 0.0)),
        model_used     = r.get("model_used", ""),
        tokens_used    = int(r.get("tokens_used", 0)),
        created_at     = r.get("created_at"),
    )


@router.post("/optimize", response_model=OptimizeResponse, dependencies=[AuthDep])
def optimize_object(body: OptimizeRequest):
    """
    Run AI optimization on a SQL object using Claude or Ollama.

    - `schema_context` is optional — when omitted the API fetches it automatically
      via the schema intelligence layer.
    - `mode` selects the optimization provider: "quick" (Ollama, fast) or "advanced" (Claude, thorough)
    - Results are persisted to `ai_optimizations` when `persist=True` (default).
    """
    from dbanalyser.ai_optimizer.optimizer import optimize_sql_object

    try:
        result = optimize_sql_object(
            object_name       = body.object_name,
            source_sql        = body.sql,
            schema_context    = body.schema_context,
            findings          = body.findings,
            execution_plan    = body.execution_plan,
            api_key           = body.api_key or "",
            model             = body.model,
            persist           = body.persist,
            optimization_mode = body.mode,
        )
    except Exception as exc:
        raise HTTPException(500, f"Optimization failed: {exc}")

    if result.error:
        return OptimizeResponse(
            object_name  = body.object_name,
            error        = result.error,
        )

    changes = [
        OptimizationChangeItem(
            type   = c.get("type", ""),
            before = c.get("before", ""),
            after  = c.get("after", ""),
            impact = c.get("impact", ""),
        )
        for c in (result.changes or [])
    ]
    return OptimizeResponse(
        object_name      = body.object_name,
        optimized_sql    = result.optimized_sql,
        reasoning        = result.reasoning or "",
        changes          = changes,
        confidence_score = float(result.confidence_score or 0.0),
        no_change_needed = bool(result.no_change_needed),
        no_change_reason = result.no_change_reason or "",
        tokens_used      = int(result.tokens_used or 0),
        model_used       = result.model_used or "",
        error            = None,
    )


@router.get("/optimizations", response_model=AiOptimizationListResponse, dependencies=[AuthDep])
def list_optimizations(
    object_name:    Optional[str] = Query(None, description="Filter by object name (partial match)"),
    db_registry_id: Optional[int] = Query(None),
    limit:          int           = Query(50, ge=1, le=500),
    offset:         int           = Query(0, ge=0),
):
    """Return a paginated history of AI optimization runs."""
    from dbanalyser.db.repository import get_ai_optimizations, count_ai_optimizations

    rows = get_ai_optimizations(object_name=object_name,
                                db_registry_id=db_registry_id,
                                limit=limit, offset=offset)
    total = count_ai_optimizations(object_name=object_name,
                                   db_registry_id=db_registry_id)
    return AiOptimizationListResponse(
        optimizations=[_to_optimization_response(r) for r in rows],
        total=total,
    )
