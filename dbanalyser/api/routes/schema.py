"""REST routes — /schema  (schema intelligence search + summary)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from dbanalyser.api.auth    import AuthDep
from dbanalyser.api.schemas import (
    OkResponse,
    SchemaObjectListResponse, SchemaObjectResponse,
    SchemaSearchRequest, SchemaSearchResponse, SchemaSearchResult,
    SchemaSummaryResponse,
)

router = APIRouter(prefix="/schema", tags=["Schema Intelligence"])


def _to_obj_response(r: dict) -> SchemaObjectResponse:
    return SchemaObjectResponse(
        id             = r["id"],
        db_registry_id = r.get("db_registry_id"),
        object_type    = r.get("object_type", ""),
        schema_name    = r.get("schema_name", "dbo"),
        object_name    = r.get("object_name", ""),
        parent_name    = r.get("parent_name", ""),
        data_type      = r.get("data_type"),
        is_nullable    = r.get("is_nullable"),
        is_primary_key = bool(r.get("is_primary_key", False)),
        is_foreign_key = bool(r.get("is_foreign_key", False)),
        definition     = r.get("definition"),
        ingested_at    = r.get("ingested_at"),
    )


@router.get("/", response_model=SchemaObjectListResponse, dependencies=[AuthDep])
def list_schema_objects(
    db_registry_id: Optional[int] = Query(None, description="Filter by database ID"),
    object_type:    Optional[str] = Query(None, description="Filter by type (table, column, procedure, …)"),
    limit:          int           = Query(200, ge=1, le=2000),
):
    """Return schema objects stored in the knowledge base."""
    from dbanalyser.schema_intel.repository import list_schema_objects
    rows = list_schema_objects(db_registry_id=db_registry_id,
                               object_type=object_type, limit=limit)
    items = [_to_obj_response(dict(r)) for r in rows]
    return SchemaObjectListResponse(objects=items, total=len(items))


@router.post("/search", response_model=SchemaSearchResponse, dependencies=[AuthDep])
def search_schema_objects(body: SchemaSearchRequest):
    """
    Semantic similarity search over the schema knowledge base.
    Returns objects most similar to the query string, ranked by cosine similarity.
    """
    from unittest.mock import patch
    from dbanalyser.schema_intel.searcher import search_schema

    try:
        results = search_schema(
            query=body.query,
            top_k=body.top_k,
            min_score=body.min_score,
            object_types=body.object_types or None,
            db_registry_id=body.db_registry_id,
        )
    except Exception as exc:
        raise HTTPException(500, f"Search failed: {exc}")

    items = [
        SchemaSearchResult(
            object_type      = r.get("object_type", ""),
            schema_name      = r.get("schema_name", "dbo"),
            object_name      = r.get("object_name", ""),
            parent_name      = r.get("parent_name", ""),
            definition       = r.get("definition"),
            similarity_score = round(float(r.get("similarity_score", 0.0)), 4),
        )
        for r in results
    ]
    return SchemaSearchResponse(query=body.query, results=items, total=len(items))


@router.get("/summary", response_model=SchemaSummaryResponse, dependencies=[AuthDep])
def schema_summary(
    db_registry_id: Optional[int] = Query(None),
):
    """Return object counts per type for the schema knowledge base."""
    from dbanalyser.schema_intel.repository import get_schema_summary
    counts = get_schema_summary(db_registry_id=db_registry_id)
    return SchemaSummaryResponse(
        db_registry_id=db_registry_id,
        counts=counts,
        total=sum(counts.values()),
    )


@router.get("/live/{db_registry_id}", dependencies=[AuthDep])
def list_objects_from_live_db(
    db_registry_id: int,
    object_type: str = Query('table', description="Object type: table, view, stored procedure, function, trigger"),
    limit: int = Query(500, ge=1, le=5000),
):
    """
    Query the actual SQL Server database for all objects of a specific type.
    Returns objects from the live database, not just ingested ones.
    """
    from dbanalyser.db.repository import get_db_registry_by_id
    from dbanalyser.db.dependency import list_objects_live

    db_entry = get_db_registry_by_id(db_registry_id)

    if not db_entry:
        raise HTTPException(status_code=404, detail=f"Database {db_registry_id} not found")

    # Build connection string
    if db_entry["use_windows_auth"]:
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={db_entry['host']},{db_entry['port']};DATABASE={db_entry['database_name']};Trusted_Connection=yes;"
    else:
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={db_entry['host']},{db_entry['port']};DATABASE={db_entry['database_name']};UID={db_entry['username']};PWD={db_entry['password']};"

    result = list_objects_live(conn_str, object_type, limit)

    if result["error"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "objects": [
            SchemaObjectResponse(
                id=0,  # Live objects don't have DB IDs
                db_registry_id=db_registry_id,
                object_type=obj["object_type"],
                schema_name=obj["schema_name"],
                object_name=obj["object_name"],
                parent_name="",
                definition=None,
                ingested_at=None,
            )
            for obj in result["objects"]
        ],
        "total": len(result["objects"]),
        "source": "live"  # Indicate this is from live DB, not ingested
    }


@router.delete("/{db_registry_id}", response_model=OkResponse, dependencies=[AuthDep])
def clear_schema_for_db(db_registry_id: int):
    """Delete all schema objects ingested for a specific database."""
    from dbanalyser.schema_intel.repository import delete_schema_for_db
    deleted = delete_schema_for_db(db_registry_id)
    return OkResponse(message=f"Deleted {deleted} schema objects for db_registry_id={db_registry_id}")


@router.post("/sync-from-snapshots", response_model=OkResponse, dependencies=[AuthDep])
def sync_schema_from_snapshots(
    db_registry_id: Optional[int] = Query(None, description="Sync for specific DB. Omit for all."),
):
    """
    Populate schema_objects table from existing object_snapshots data.
    This lets Schema Quality and Object Dependencies work without a full metadata refresh.
    """
    from dbanalyser.db.connection import get_cursor
    inserted = 0
    try:
        with get_cursor() as cur:
            # Build filter clause
            where = "WHERE os.run_id IN (SELECT id FROM runs WHERE db_registry_id = %s)" if db_registry_id else ""
            params = [db_registry_id] if db_registry_id else []

            cur.execute(f"""
                SELECT DISTINCT
                    r.db_registry_id,
                    os.object_type,
                    COALESCE(os.schema_name, 'dbo') AS schema_name,
                    os.object_name,
                    '' AS parent_name
                FROM object_snapshots os
                JOIN runs r ON r.id = os.run_id
                {where}
                AND r.db_registry_id IS NOT NULL
                AND os.object_name IS NOT NULL
            """, params)
            rows = cur.fetchall()

            for row in rows:
                db_reg_id = row["db_registry_id"]
                obj_type = (row["object_type"] or "").lower()
                schema_name = row["schema_name"] or "dbo"
                object_name = row["object_name"] or ""
                if not object_name:
                    continue
                try:
                    cur.execute("""
                        INSERT INTO schema_objects
                            (db_registry_id, object_type, schema_name, object_name,
                             parent_name, embedding_json)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (db_registry_id, object_type, schema_name, object_name, parent_name)
                        DO UPDATE SET ingested_at = NOW()
                    """, (db_reg_id, obj_type, schema_name, object_name, "", "[]"))
                    inserted += 1
                except Exception:
                    pass  # Skip individual insert errors

        return OkResponse(message=f"Synced {inserted} schema objects from snapshots.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}")

