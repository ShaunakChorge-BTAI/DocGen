"""REST routes — /metadata (schema metadata and refresh operations)."""

from __future__ import annotations

import logging
import hashlib
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from dbanalyser.api.auth    import AuthDep
from dbanalyser.api.schemas import OkResponse
from dbanalyser.db.connection import get_cursor
from dbanalyser.db.repository import get_db_registry
from dbanalyser.db.driver_factory import get_driver
from dbanalyser.schema_intel.adapter_factory import get_schema_adapter
from dbanalyser.config import DatabaseEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metadata", tags=["Metadata"])


@router.post("/{db_name}/refresh", response_model=OkResponse, dependencies=[AuthDep])
def refresh_database_metadata(db_name: str):
    """Fetch and store metadata for specified database (async).

    Refreshes:
    - Tables and columns
    - Stored procedures and functions
    - Views
    - Indexes

    Returns a job_id for polling progress.
    """
    # Get database registry entry
    row = get_db_registry(db_name)
    if not row:
        raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found.")

    # Create DatabaseEntry from registry row
    db_entry = DatabaseEntry(
        name              = row['name'],
        db_type           = row.get('db_type', 'mssql'),
        environment       = row['environment'],
        host              = row['host'],
        port              = row.get('port'),
        database_name     = row['database_name'],
        connection_string = row.get('connection_string'),
        use_windows_auth  = row.get('use_windows_auth', False),
        username          = row.get('username'),
        password          = row.get('password'),
        oracle_sid_or_service = row.get('oracle_sid_or_service'),
        snowflake_warehouse   = row.get('snowflake_warehouse'),
        snowflake_role        = row.get('snowflake_role'),
    )

    try:
        # Get driver and test connection
        driver = get_driver(db_entry)
        if not driver.test_connection():
            raise HTTPException(status_code=400, detail="Failed to connect to database. Check credentials.")

        # Get schema adapter and extract metadata
        adapter = get_schema_adapter(db_entry.db_type, driver)
        metadata = adapter.extract_schema()

        # Store in object_snapshots
        cursor = get_cursor()
        timestamp_iso = datetime.utcnow().isoformat()

        # Create a run record for this metadata refresh
        run_sql = """
            INSERT INTO runs (run_id, db_registry_id, label, timestamp, source_mode, status, total_objects)
            VALUES (%s, %s, %s, %s, 'metadata', 'success', %s)
            RETURNING id
        """
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        cursor.execute(run_sql, (run_id, row['id'], f"Metadata Refresh - {db_name}", timestamp_iso, metadata.total_objects))
        cursor_result = cursor.fetchone()
        if cursor_result:
            run_pk = cursor_result[0]
        else:
            raise Exception("Failed to create run record")

        # Insert metadata refresh log
        refresh_log_sql = """
            INSERT INTO metadata_refresh_log (db_registry_id, timestamp, status, objects_fetched)
            VALUES (%s, %s, 'success', %s)
        """
        cursor.execute(refresh_log_sql, (row['id'], timestamp_iso, metadata.total_objects))

        # Store tables as object_snapshots
        for table in metadata.tables:
            metadata_hash = hashlib.sha256(
                json.dumps([(c.name, c.data_type) for c in table.columns]).encode()
            ).hexdigest()

            snapshot_sql = """
                INSERT INTO object_snapshots (
                    run_id, object_name, object_type, schema_name,
                    snapshot_type, source_db_type, metadata_hash, created_at
                ) VALUES (%s, %s, 'Table', %s, 'metadata_fetch', %s, %s, %s)
                ON CONFLICT DO NOTHING
            """
            cursor.execute(snapshot_sql, (
                run_pk, table.name, table.schema,
                db_entry.db_type, metadata_hash, timestamp_iso
            ))

        # Store procedures
        for proc in metadata.procedures:
            snapshot_sql = """
                INSERT INTO object_snapshots (
                    run_id, object_name, object_type, schema_name,
                    snapshot_type, source_db_type, created_at
                ) VALUES (%s, %s, 'Procedure', %s, 'metadata_fetch', %s, %s)
                ON CONFLICT DO NOTHING
            """
            cursor.execute(snapshot_sql, (
                run_pk, proc.name, proc.schema,
                db_entry.db_type, timestamp_iso
            ))

        # Store views
        for view in metadata.views:
            snapshot_sql = """
                INSERT INTO object_snapshots (
                    run_id, object_name, object_type, schema_name,
                    snapshot_type, source_db_type, created_at
                ) VALUES (%s, %s, 'View', %s, 'metadata_fetch', %s, %s)
                ON CONFLICT DO NOTHING
            """
            cursor.execute(snapshot_sql, (
                run_pk, view.name, view.schema,
                db_entry.db_type, timestamp_iso
            ))

        # Store indexes
        for index in metadata.indexes:
            snapshot_sql = """
                INSERT INTO object_snapshots (
                    run_id, object_name, object_type, schema_name,
                    snapshot_type, source_db_type, created_at
                ) VALUES (%s, %s, 'Index', %s, 'metadata_fetch', %s, %s)
                ON CONFLICT DO NOTHING
            """
            cursor.execute(snapshot_sql, (
                run_pk, index.name, index.table_schema,
                db_entry.db_type, timestamp_iso
            ))

        cursor.connection.commit()
        cursor.close()
        driver.disconnect()

        return OkResponse(message=f"Metadata refresh complete. {metadata.total_objects} objects fetched.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Metadata refresh failed for {db_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Metadata refresh failed: {str(e)}")


@router.get("/{db_name}", dependencies=[AuthDep])
def get_database_metadata(db_name: str, object_type: Optional[str] = None):
    """Fetch latest schema metadata for database.

    Query params:
    - object_type: filter by type (Table, Procedure, View, Index)
    """
    row = get_db_registry(db_name)
    if not row:
        raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found.")

    cursor = get_cursor()
    try:
        # Get latest run for this database
        sql = """
            SELECT id, timestamp FROM runs
            WHERE db_registry_id = %s AND source_mode = 'metadata'
            ORDER BY timestamp DESC
            LIMIT 1
        """
        cursor.execute(sql, (row['id'],))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail=f"No metadata found for database '{db_name}'.")

        run_id, last_updated = result

        # Get object snapshots
        sql = """
            SELECT object_name, object_type, schema_name, metadata_hash, created_at
            FROM object_snapshots
            WHERE run_id = %s AND snapshot_type = 'metadata_fetch'
        """
        params = [run_id]
        if object_type:
            sql += " AND object_type = %s"
            params.append(object_type)
        sql += " ORDER BY object_type, schema_name, object_name"

        cursor.execute(sql, params)
        objects = cursor.fetchall()

        # Group by type
        grouped = {}
        for obj in objects:
            obj_type = obj[1]
            if obj_type not in grouped:
                grouped[obj_type] = []
            grouped[obj_type].append({
                'name': obj[0],
                'schema': obj[2],
                'hash': obj[3],
                'fetched_at': obj[4].isoformat() if obj[4] else None
            })

        return {
            'db_name': db_name,
            'last_updated': last_updated.isoformat() if last_updated else None,
            'objects': grouped,
        }
    finally:
        cursor.close()
