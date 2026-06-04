"""REST routes — /schedules  (scan schedule CRUD + manual trigger)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, BackgroundTasks

from dbanalyser.api.auth    import AuthDep
from dbanalyser.api.schemas import (
    ScheduledTaskCreate, ScheduledTaskResponse, OkResponse, JobStatusResponse,
)

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.get("", response_model=List[ScheduledTaskResponse], dependencies=[AuthDep])
def list_schedules():
    """List all scheduled analysis tasks."""
    from dbanalyser.db.repository import list_schedules as _list
    rows = _list()
    return [_to_response(r) for r in rows]


@router.post("", response_model=ScheduledTaskResponse, dependencies=[AuthDep])
def create_or_update_schedule(body: ScheduledTaskCreate):
    """Create or update a scheduled task (keyed by db_name)."""
    from dbanalyser.db.repository import upsert_schedule
    row = upsert_schedule(
        db_name  = body.db_name,
        schedule = body.schedule,
        label    = body.label,
        enabled  = body.enabled,
        run_dmv  = body.run_dmv,
        formats  = body.formats,
    )
    return _to_response(row)


@router.delete("/{schedule_id}", response_model=OkResponse, dependencies=[AuthDep])
def delete_schedule(schedule_id: int):
    """Delete a scheduled task by ID."""
    from dbanalyser.db.repository import delete_schedule as _delete
    found = _delete(schedule_id)
    if not found:
        raise HTTPException(404, f"Schedule {schedule_id} not found.")
    return OkResponse(message=f"Schedule {schedule_id} deleted.")


@router.patch("/{schedule_id}/toggle", response_model=OkResponse, dependencies=[AuthDep])
def toggle_schedule(schedule_id: int, enabled: bool):
    """Enable or disable a scheduled task."""
    from dbanalyser.db.repository import toggle_schedule as _toggle
    found = _toggle(schedule_id, enabled)
    if not found:
        raise HTTPException(404, f"Schedule {schedule_id} not found.")
    return OkResponse(message=f"Schedule {schedule_id} {'enabled' if enabled else 'disabled'}.")


@router.post("/{schedule_id}/trigger", response_model=JobStatusResponse, dependencies=[AuthDep])
def trigger_schedule_now(schedule_id: int, background_tasks: BackgroundTasks):
    """Immediately trigger the analysis run for a scheduled task."""
    from dbanalyser.db.repository import list_schedules, mark_schedule_ran
    rows = list_schedules()
    row  = next((r for r in rows if r["id"] == schedule_id), None)
    if not row:
        raise HTTPException(404, f"Schedule {schedule_id} not found.")

    # Re-use the runs trigger endpoint logic
    from dbanalyser.api.routes.runs import trigger_analysis, _JOBS
    from dbanalyser.api.schemas     import RunTriggerRequest
    import uuid

    req = RunTriggerRequest(
        db_name = row["db_name"],
        label   = row.get("label") or "",
        run_dmv = bool(row.get("run_dmv", False)),
        formats = list(row.get("formats") or ["json"]),
    )
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {"status": "queued", "message": "Job queued", "run_id": None}

    from dbanalyser.api.routes.runs import _run_job
    background_tasks.add_task(_run_job, job_id, req)

    # Update last_run immediately
    mark_schedule_ran(schedule_id)

    return JobStatusResponse(job_id=job_id, status="queued",
                             message=f"Schedule '{row['db_name']}' triggered.")


# ── helpers ──────────────────────────────────────────────────────────────────

def _to_response(row: dict) -> ScheduledTaskResponse:
    import json
    formats = row.get("formats") or ["json"]
    if isinstance(formats, str):
        try:
            formats = json.loads(formats)
        except Exception:
            formats = ["json"]
    return ScheduledTaskResponse(
        id         = row["id"],
        db_name    = row["db_name"],
        schedule   = row.get("schedule", "manual"),
        label      = row.get("label", ""),
        enabled    = bool(row.get("enabled", True)),
        run_dmv    = bool(row.get("run_dmv", False)),
        formats    = formats,
        last_run   = row.get("last_run"),
        next_run   = row.get("next_run"),
        created_at = row.get("created_at"),
    )
