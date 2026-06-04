"""REST routes — /pipeline  (pipeline step tracking per run)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dbanalyser.api.auth    import AuthDep
from dbanalyser.api.schemas import PipelineResponse, PipelineStepResponse

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


def _to_step_response(r: dict) -> PipelineStepResponse:
    return PipelineStepResponse(
        id           = r["id"],
        run_id       = r["run_id"],
        step         = r.get("step", ""),
        status       = r.get("status", "pending"),
        started_at   = r.get("started_at"),
        completed_at = r.get("completed_at"),
        duration_sec = r.get("duration_sec"),
        error        = r.get("error"),
        details      = r.get("details") or {},
    )


@router.get("/{run_id}", response_model=PipelineResponse, dependencies=[AuthDep])
def get_pipeline_for_run(run_id: int):
    """
    Return the pipeline steps recorded for a specific analysis run.

    Steps are ordered by insertion time (earliest first).
    """
    from dbanalyser.db.repository import get_pipeline_steps
    rows = get_pipeline_steps(run_id)
    return PipelineResponse(
        run_id = run_id,
        steps  = [_to_step_response(r) for r in rows],
        total  = len(rows),
    )
