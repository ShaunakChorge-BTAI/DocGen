"""REST routes — /trend  (health-score time series per database)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from dbanalyser.api.auth    import AuthDep
from dbanalyser.api.schemas import TrendPoint, TrendResponse
from dbanalyser.db.repository import (
    get_trend_for_db, get_trend_all_dbs, get_db_registry,
)

router = APIRouter(prefix="/trend", tags=["Trend"])


def _row_to_point(r: dict) -> TrendPoint:
    return TrendPoint(
        timestamp       = r["timestamp"],
        health_score    = r.get("health_score"),
        total_issues    = r.get("total_issues", 0),
        critical_count  = r.get("critical_count", 0),
        high_count      = r.get("high_count", 0),
        medium_count    = r.get("medium_count", 0),
        low_count       = r.get("low_count", 0),
        new_issues      = r.get("new_issues", 0),
        resolved_issues = r.get("resolved_issues", 0),
        db_name         = r.get("db_name") or r.get("db_name_label"),
    )


@router.get("/all", response_model=List[TrendResponse], dependencies=[AuthDep])
def trend_all_databases():
    """Latest trend point for every registered database — for the estate heatmap."""
    import pandas as pd
    df = get_trend_all_dbs()
    if isinstance(df, pd.DataFrame):
        rows = df.fillna("").to_dict(orient="records")
    else:
        rows = df or []
    # Group by database
    grouped: dict[str, list] = {}
    for r in rows:
        key = r.get("db_name_label") or r.get("db_name") or str(r.get("db_registry_id",""))
        grouped.setdefault(key, []).append(r)
    return [
        TrendResponse(db_name=name, points=[_row_to_point(r) for r in pts])
        for name, pts in grouped.items()
    ]


@router.get("/{db_name}", response_model=TrendResponse, dependencies=[AuthDep])
def trend_for_database(
    db_name: str,
    limit:   int = Query(60, ge=1, le=365, description="Max data points to return"),
):
    """Full trend history for a single database (newest to oldest)."""
    row = get_db_registry(db_name)
    if not row:
        raise HTTPException(404, f"Database '{db_name}' not found in registry.")
    db_id = row["id"]

    import pandas as pd
    df = get_trend_for_db(db_id, limit=limit)
    if isinstance(df, pd.DataFrame):
        rows = df.fillna("").to_dict(orient="records")
    else:
        rows = df or []

    # Sort chronologically for chart rendering
    rows.sort(key=lambda r: r.get("timestamp") or "")
    return TrendResponse(
        db_name = db_name,
        points  = [_row_to_point(r) for r in rows],
    )
