"""REST routes — /databases  (db_registry CRUD)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Path

from dbanalyser.api.auth    import AuthDep
from dbanalyser.api.schemas import (
    DbRegistryCreate, DbRegistryResponse, EstateSummaryResponse,
    DbSummaryItem, OkResponse,
)
from dbanalyser.db.connection import get_cursor
from dbanalyser.db.models     import DbRegistry
from dbanalyser.db.repository import (
    upsert_db_registry, get_db_registry, list_db_registries,
    delete_db_registry, get_db_summary, get_db_registry_by_id,
    hard_delete_db_registry, hard_delete_run,
)
from dbanalyser.db.driver_factory import get_driver
from dbanalyser.config import DatabaseEntry

router = APIRouter(prefix="/databases", tags=["Databases"])


@router.get("", response_model=List[DbRegistryResponse], dependencies=[AuthDep])
def list_databases(active_only: bool = Query(False)):
    """List all registered databases."""
    rows = list_db_registries(active_only=active_only)
    return [DbRegistryResponse(**r) for r in rows]


@router.get("/summary", response_model=EstateSummaryResponse, dependencies=[AuthDep])
def estate_summary():
    """Estate-wide summary — one row per registered database with latest run stats."""
    rows = get_db_summary()
    import statistics
    health_vals = [r["health_score"] for r in rows if r.get("health_score") is not None]
    return EstateSummaryResponse(
        total_databases = len(rows),
        avg_health      = round(statistics.mean(health_vals), 1) if health_vals else None,
        total_findings  = sum(r.get("total_issues", 0) or 0  for r in rows),
        total_critical  = sum(r.get("critical_count", 0) or 0 for r in rows),
        databases       = [DbSummaryItem(**{
            "id":             r["id"],
            "name":           r["name"],
            "environment":    r.get("environment", ""),
            "owner_label":    r.get("owner_label"),
            "health_score":   r.get("health_score"),
            "critical_count": r.get("critical_count"),
            "high_count":     r.get("high_count"),
            "total_issues":   r.get("total_issues"),
            "total_objects":  r.get("total_objects"),
            "last_run_ts":    r.get("last_run_ts"),
            "is_active":      r.get("is_active", True),
        }) for r in rows],
    )


@router.post("/validate", response_model=OkResponse, dependencies=[AuthDep])
def test_database_connection(body: DbRegistryCreate):
    """Test database connection with provided credentials."""
    # Create temporary DatabaseEntry from request
    db_entry = DatabaseEntry(
        name              = body.name or "test",
        db_type           = body.db_type,
        environment       = body.environment,
        host              = body.host,
        port              = body.port,
        database_name     = body.database_name,
        connection_string = body.connection_string or "",
        use_windows_auth  = body.use_windows_auth,
        username          = body.username or "",
        password          = body.password or "",
        oracle_sid_or_service = body.oracle_sid_or_service,
        snowflake_warehouse   = body.snowflake_warehouse,
        snowflake_role        = body.snowflake_role,
    )

    # Validate config
    driver = get_driver(db_entry)
    is_valid, error_msg = driver.validate_config()
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {error_msg}")

    # Test connection
    if not driver.test_connection():
        raise HTTPException(status_code=400, detail="Connection test failed. Check credentials and settings.")

    return OkResponse(message="Connection test successful.")


@router.post("", response_model=DbRegistryResponse, dependencies=[AuthDep])
def create_or_update_database(body: DbRegistryCreate):
    """Register (or update) a database. Name is the unique key."""
    # Validate config
    db_entry = DatabaseEntry(
        name              = body.name or "temp",
        db_type           = body.db_type,
        environment       = body.environment,
        host              = body.host,
        port              = body.port,
        database_name     = body.database_name,
        connection_string = body.connection_string or "",
        use_windows_auth  = body.use_windows_auth,
        username          = body.username or "",
        password          = body.password or "",
        oracle_sid_or_service = body.oracle_sid_or_service,
        snowflake_warehouse   = body.snowflake_warehouse,
        snowflake_role        = body.snowflake_role,
    )
    driver = get_driver(db_entry)
    is_valid, error_msg = driver.validate_config()
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {error_msg}")

    # Test connection before saving
    if not driver.test_connection():
        raise HTTPException(status_code=400, detail="Connection test failed. Check credentials and settings.")

    reg = DbRegistry(
        id                     = body.id,
        name                   = body.name,
        db_type                = body.db_type,
        environment            = body.environment,
        host                   = body.host,
        port                   = body.port,
        database_name          = body.database_name,
        connection_string      = body.connection_string,
        use_windows_auth       = body.use_windows_auth,
        username               = body.username,
        password               = body.password,
        oracle_sid_or_service  = body.oracle_sid_or_service,
        snowflake_warehouse    = body.snowflake_warehouse,
        snowflake_role         = body.snowflake_role,
        description            = body.description,
        owner_label            = body.owner_label,
        tags                   = body.tags,
        is_active              = body.is_active,
    )
    db_id = upsert_db_registry(reg)
    row   = get_db_registry_by_id(db_id)
    # Exclude password from response
    row.pop("password", None)
    return DbRegistryResponse(**row)


@router.delete("/{name}", response_model=OkResponse, dependencies=[AuthDep])
def deactivate_database(name: str):
    """Soft-delete (deactivate) a database from the registry by name."""
    found = delete_db_registry(name)
    if not found:
        raise HTTPException(status_code=404, detail=f"Database '{name}' not found.")
    return OkResponse(message=f"Database '{name}' deactivated.")


@router.delete("/{db_registry_id}/hard-delete", response_model=OkResponse, dependencies=[AuthDep])
def hard_delete_database(db_registry_id: int):
    """
    Hard delete: Permanently and IRREVERSIBLY delete a database registry and ALL associated scan data.

    Deletes:
      - All runs for this database
      - All findings, snapshots, health trends, pipeline steps associated with those runs
      - The database registry itself

    WARNING: This action cannot be undone. Use with caution.
    """
    try:
        counts = hard_delete_db_registry(db_registry_id)
        message = (
            f"Deleted database (id={db_registry_id}). "
            f"Removed: {counts.get('runs', 0)} runs, "
            f"{counts.get('findings', 0)} findings, "
            f"{counts.get('snapshots', 0)} snapshots, "
            f"{counts.get('health_trend', 0)} health records."
        )
        return OkResponse(message=message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Hard delete failed: {exc}")


@router.delete("/runs/{run_id}/hard-delete", response_model=OkResponse, dependencies=[AuthDep])
def hard_delete_analysis_run(run_id: int):
    """
    Hard delete: Permanently and IRREVERSIBLY delete a single analysis run and its data.

    Deletes:
      - The run record
      - All findings, snapshots, health trends, pipeline steps for this run

    WARNING: This action cannot be undone.
    """
    try:
        counts = hard_delete_run(run_id)
        if counts.get("runs", 0) == 0:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

        message = (
            f"Deleted run (id={run_id}). "
            f"Removed: {counts.get('findings', 0)} findings, "
            f"{counts.get('snapshots', 0)} snapshots, "
            f"{counts.get('health_trend', 0)} health records."
        )
        return OkResponse(message=message)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Hard delete failed: {exc}")


@router.get("/{name}", response_model=DbRegistryResponse, dependencies=[AuthDep])
def get_database(name: str):
    """Get a single registered database by name."""
    # Reject reserved names
    if name in ["test-connection", "summary", "runs"]:
        raise HTTPException(status_code=404, detail=f"Database '{name}' not found.")
    row = get_db_registry(name)
    if not row:
        raise HTTPException(status_code=404, detail=f"Database '{name}' not found.")
    return DbRegistryResponse(**row)
