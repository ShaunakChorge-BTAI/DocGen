"""REST routes — /live-metrics (real-time performance metrics capture)."""

from __future__ import annotations

import logging
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from dbanalyser.api.auth import AuthDep
from dbanalyser.api.schemas import OkResponse
from dbanalyser.db.connection import get_cursor
from dbanalyser.db.repository import get_db_registry
from dbanalyser.db.driver_factory import get_driver
from dbanalyser.engine.monitor_factory import get_monitor
from dbanalyser.config import DatabaseEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-metrics", tags=["Live Metrics"])


from pydantic import BaseModel

class ScanRequest(BaseModel):
    metric_types: Optional[List[str]] = None

@router.post("/{db_name}/scan", dependencies=[AuthDep])
def scan_live_metrics(db_name: str, req: Optional[ScanRequest] = None):
    metric_types = req.metric_types if req else None
    """Capture live performance metrics for specified database.

    Captures index usage, missing indexes, slow queries, blocking sessions,
    wait statistics, and table sizes.

    Metric types:
    - index_usage: Index seeks, scans, lookups, updates
    - unused_indexes: Indexes with zero usage
    - missing_indexes: Recommended missing indexes
    - slow_queries: Slow queries by duration
    - blocking_sessions: Active blocking chains
    - wait_statistics: Wait type breakdown
    - table_sizes: Table row counts and disk usage

    Returns a run_id for tracking the metrics capture job.
    """
    # Get database registry entry
    row = get_db_registry(db_name)
    if not row:
        raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found.")

    # Create DatabaseEntry from registry row
    db_entry = DatabaseEntry(
        name=row.get('name') or 'temp',
        db_type=row.get('db_type') or 'mssql',
        environment=row.get('environment') or 'development',
        host=row.get('host') or 'localhost',
        port=row.get('port'),
        database_name=row.get('database_name') or '',
        connection_string=row.get('connection_string') or '',
        use_windows_auth=bool(row.get('use_windows_auth')),
        username=row.get('username') or '',
        password=row.get('password') or '',
        oracle_sid_or_service=row.get('oracle_sid_or_service'),
        snowflake_warehouse=row.get('snowflake_warehouse'),
        snowflake_role=row.get('snowflake_role'),
    )

    try:
        # Get driver and test connection
        driver = get_driver(db_entry)
        if not driver.test_connection():
            raise HTTPException(status_code=400, detail="Failed to connect to database. Check credentials.")

        # Get monitor adapter and capture metrics
        monitor = get_monitor(db_entry.db_type, driver)
        timestamp_iso = datetime.utcnow().isoformat()

        # Create a run record for this metrics capture
        with get_cursor() as cursor:
            run_sql = """
                INSERT INTO runs (run_id, db_registry_id, label, timestamp, source_mode, status, total_objects)
                VALUES (%s, %s, %s, %s, 'live_metrics', 'success', 0)
                RETURNING id
            """
            run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S_metrics")
            cursor.execute(run_sql, (run_id, row['id'], f"Live Metrics - {db_name}", timestamp_iso))
            cursor_result = cursor.fetchone()
            if cursor_result:
                run_pk = cursor_result[0]
            else:
                raise Exception("Failed to create run record")

            # Default to all metrics if not specified
            if not metric_types:
                metric_types = [
                    'index_usage',
                    'unused_indexes',
                    'missing_indexes',
                    'slow_queries',
                    'blocking_sessions',
                    'wait_statistics',
                    'table_sizes',
                ]

            metrics_captured = 0
            captured_data = {
                'index_usage': [],
                'unused_indexes': [],
                'missing_indexes': [],
                'slow_queries': [],
                'blocking_sessions': [],
                'wait_statistics': [],
                'table_sizes': [],
            }

            # Capture each requested metric type
            if 'index_usage' in metric_types:
                try:
                    indexes = monitor.get_index_statistics(limit=100)
                    for idx in indexes:
                        metrics_captured += 1
                        dmv_sql = """
                            INSERT INTO dmv_snapshots (
                                run_id, dmv_type, data_json, db_type, source_system, created_at
                            ) VALUES (%s, %s, %s, %s, 'live_monitor', %s)
                        """
                        metric_data = {
                            'index_name': idx.index_name,
                            'table_name': idx.table_name,
                            'schema_name': idx.schema_name,
                            'seeks': idx.seeks,
                            'scans': idx.scans,
                            'lookups': idx.lookups,
                            'updates': idx.updates,
                            'size_mb': idx.size_mb,
                            'is_unique': idx.is_unique,
                            'is_primary_key': idx.is_primary_key,
                        }
                        captured_data['index_usage'].append(metric_data)
                        cursor.execute(
                            dmv_sql,
                            (run_pk, 'index_usage', json.dumps(metric_data), db_entry.db_type, timestamp_iso)
                        )
                except Exception as e:
                    logger.error(f"Failed to capture index_usage metrics: {e}")

            if 'unused_indexes' in metric_types:
                try:
                    unused = monitor.get_unused_indexes(limit=50)
                    for idx in unused:
                        metrics_captured += 1
                        dmv_sql = """
                            INSERT INTO dmv_snapshots (
                                run_id, dmv_type, data_json, db_type, source_system, created_at
                            ) VALUES (%s, %s, %s, %s, 'live_monitor', %s)
                        """
                        metric_data = {
                            'index_name': idx.index_name,
                            'table_name': idx.table_name,
                            'schema_name': idx.schema_name,
                            'size_mb': idx.size_mb,
                        }
                        captured_data['unused_indexes'].append(metric_data)
                        cursor.execute(
                            dmv_sql,
                            (run_pk, 'unused_indexes', json.dumps(metric_data), db_entry.db_type, timestamp_iso)
                        )
                except Exception as e:
                    logger.error(f"Failed to capture unused_indexes metrics: {e}")

            if 'missing_indexes' in metric_types:
                try:
                    missing = monitor.get_missing_indexes(limit=20)
                    for idx in missing:
                        metrics_captured += 1
                        dmv_sql = """
                            INSERT INTO dmv_snapshots (
                                run_id, dmv_type, data_json, db_type, source_system, created_at
                            ) VALUES (%s, %s, %s, %s, 'live_monitor', %s)
                        """
                        metric_data = {
                            'table_name': idx.table_name,
                            'schema_name': idx.schema_name,
                            'column_list': idx.column_list,
                            'include_columns': idx.include_column_list,
                            'estimated_improvement_percent': idx.estimated_improvement_percent,
                            'recommendation': idx.recommendation,
                        }
                        captured_data['missing_indexes'].append(metric_data)
                        cursor.execute(
                            dmv_sql,
                            (run_pk, 'missing_indexes', json.dumps(metric_data), db_entry.db_type, timestamp_iso)
                        )
                except Exception as e:
                    logger.error(f"Failed to capture missing_indexes metrics: {e}")

            if 'slow_queries' in metric_types:
                try:
                    slow_queries = monitor.get_slow_queries(top_n=50)
                    for query in slow_queries:
                        metrics_captured += 1
                        dmv_sql = """
                            INSERT INTO dmv_snapshots (
                                run_id, dmv_type, data_json, db_type, source_system, created_at
                            ) VALUES (%s, %s, %s, %s, 'live_monitor', %s)
                        """
                        metric_data = {
                            'query_hash': query.query_hash,
                            'query_text': query.query_text[:1000],  # Limit to 1000 chars
                            'execution_count': query.execution_count,
                            'avg_duration_ms': query.avg_duration_ms,
                            'total_duration_ms': query.total_duration_ms,
                            'avg_cpu_ms': query.avg_cpu_ms,
                        }
                        captured_data['slow_queries'].append(metric_data)
                        cursor.execute(
                            dmv_sql,
                            (run_pk, 'slow_queries', json.dumps(metric_data), db_entry.db_type, timestamp_iso)
                        )
                except Exception as e:
                    logger.error(f"Failed to capture slow_queries metrics: {e}")

            if 'blocking_sessions' in metric_types:
                try:
                    blocking = monitor.get_blocking_sessions()
                    for session in blocking:
                        metrics_captured += 1
                        dmv_sql = """
                            INSERT INTO dmv_snapshots (
                                run_id, dmv_type, data_json, db_type, source_system, created_at
                            ) VALUES (%s, %s, %s, %s, 'live_monitor', %s)
                        """
                        metric_data = {
                            'session_id': session.session_id,
                            'database_name': session.database_name,
                            'user_name': session.user_name,
                            'program_name': session.program_name,
                            'host_name': session.host_name,
                            'status': session.status,
                            'wait_type': session.wait_type,
                            'wait_duration_ms': session.wait_duration_ms,
                            'blocking_session_id': session.blocking_session_id,
                        }
                        captured_data['blocking_sessions'].append(metric_data)
                        cursor.execute(
                            dmv_sql,
                            (run_pk, 'blocking_sessions', json.dumps(metric_data), db_entry.db_type, timestamp_iso)
                        )
                except Exception as e:
                    logger.error(f"Failed to capture blocking_sessions metrics: {e}")

            if 'wait_statistics' in metric_types:
                try:
                    waits = monitor.get_wait_statistics(limit=50)
                    for wait in waits:
                        metrics_captured += 1
                        dmv_sql = """
                            INSERT INTO dmv_snapshots (
                                run_id, dmv_type, data_json, db_type, source_system, created_at
                            ) VALUES (%s, %s, %s, %s, 'live_monitor', %s)
                        """
                        metric_data = {
                            'wait_type': wait.wait_type,
                            'wait_count': wait.wait_count,
                            'wait_time_ms': wait.wait_time_ms,
                            'avg_wait_ms': wait.avg_wait_ms,
                        }
                        captured_data['wait_statistics'].append(metric_data)
                        cursor.execute(
                            dmv_sql,
                            (run_pk, 'wait_statistics', json.dumps(metric_data), db_entry.db_type, timestamp_iso)
                        )
                except Exception as e:
                    logger.error(f"Failed to capture wait_statistics metrics: {e}")

            if 'table_sizes' in metric_types:
                try:
                    tables = monitor.get_table_sizes(limit=100)
                    for table in tables:
                        metrics_captured += 1
                        dmv_sql = """
                            INSERT INTO dmv_snapshots (
                                run_id, dmv_type, data_json, db_type, source_system, created_at
                            ) VALUES (%s, %s, %s, %s, 'live_monitor', %s)
                        """
                        metric_data = {
                            'table_name': table.table_name,
                            'schema_name': table.schema_name,
                            'row_count': table.row_count,
                            'reserved_mb': table.reserved_mb,
                            'used_mb': table.used_mb,
                            'data_mb': table.data_mb,
                            'index_mb': table.index_mb,
                        }
                        captured_data['table_sizes'].append(metric_data)
                        cursor.execute(
                            dmv_sql,
                            (run_pk, 'table_sizes', json.dumps(metric_data), db_entry.db_type, timestamp_iso)
                        )
                except Exception as e:
                    logger.error(f"Failed to capture table_sizes metrics: {e}")

        driver.disconnect()

        return {
            "ok": True,
            "message": f"Live metrics capture complete. {metrics_captured} metric records captured.",
            "captured_metrics": {
                "blocking_sessions": captured_data["blocking_sessions"],
                "slow_queries": captured_data["slow_queries"],
                "largest_tables": [
                    {
                        "table_name": t["table_name"],
                        "schema_name": t["schema_name"],
                        "row_count": t["row_count"],
                        "used_mb": t["used_mb"],
                    }
                    for t in captured_data["table_sizes"]
                ],
                "index_usage": captured_data["index_usage"],
                "unused_indexes": captured_data["unused_indexes"],
                "missing_indexes": [
                    {
                        "table_name": idx["table_name"],
                        "schema_name": idx["schema_name"],
                        "column_list": idx["column_list"],
                        "recommendation": idx["recommendation"],
                        "estimated_improvement_percent": idx["estimated_improvement_percent"],
                    }
                    for idx in captured_data["missing_indexes"]
                ],
                "wait_statistics": captured_data["wait_statistics"],
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Live metrics capture failed for {db_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Live metrics capture failed: {str(e)}")


@router.get("/{db_name}/live-status", dependencies=[AuthDep])
def get_database_live_status(db_name: str):
    """Get current live status snapshot for database.

    Returns blocking sessions, slow queries, and table sizes without async job.
    """
    # Get database registry entry
    row = get_db_registry(db_name)
    if not row:
        raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found.")

    # Create DatabaseEntry from registry row
    db_entry = DatabaseEntry(
        name=row.get('name') or 'temp',
        db_type=row.get('db_type') or 'mssql',
        environment=row.get('environment') or 'development',
        host=row.get('host') or 'localhost',
        port=row.get('port'),
        database_name=row.get('database_name') or '',
        connection_string=row.get('connection_string') or '',
        use_windows_auth=bool(row.get('use_windows_auth')),
        username=row.get('username') or '',
        password=row.get('password') or '',
        oracle_sid_or_service=row.get('oracle_sid_or_service'),
        snowflake_warehouse=row.get('snowflake_warehouse'),
        snowflake_role=row.get('snowflake_role'),
    )

    try:
        # Get driver and test connection
        driver = get_driver(db_entry)
        if not driver.test_connection():
            raise HTTPException(status_code=400, detail="Failed to connect to database. Check credentials.")



        # Get monitor adapter and capture key metrics
        monitor = get_monitor(db_entry.db_type, driver)

        blocking_sessions = monitor.get_blocking_sessions()
        slow_queries = monitor.get_slow_queries(top_n=10)
        table_sizes = monitor.get_table_sizes(limit=20)
        index_usage = monitor.get_index_statistics(limit=20)
        unused_indexes = monitor.get_unused_indexes(limit=20)
        missing_indexes = monitor.get_missing_indexes(limit=20)
        wait_statistics = monitor.get_wait_statistics(limit=20)

        driver.disconnect()

        return {
            'db_name': db_name,
            'db_type': db_entry.db_type,
            'timestamp': datetime.utcnow().isoformat(),
            'blocking_sessions': [
                {
                    'session_id': s.session_id,
                    'user_name': s.user_name,
                    'program_name': s.program_name,
                    'status': s.status,
                    'wait_duration_ms': s.wait_duration_ms,
                    'blocking_session_id': s.blocking_session_id,
                }
                for s in blocking_sessions
            ],
            'slow_queries': [
                {
                    'query_hash': q.query_hash,
                    'query_text': q.query_text[:200],
                    'total_duration_ms': q.total_duration_ms,
                    'execution_count': q.execution_count,
                }
                for q in slow_queries
            ],
            'largest_tables': [
                {
                    'table_name': t.table_name,
                    'schema_name': t.schema_name,
                    'row_count': t.row_count,
                    'used_mb': t.used_mb,
                }
                for t in table_sizes
            ],
            'index_usage': [
                {
                    'index_name': idx.index_name,
                    'table_name': idx.table_name,
                    'schema_name': idx.schema_name,
                    'seeks': idx.seeks,
                    'scans': idx.scans,
                    'updates': idx.updates,
                    'size_mb': idx.size_mb,
                }
                for idx in index_usage
            ],
            'unused_indexes': [
                {
                    'index_name': idx.index_name,
                    'table_name': idx.table_name,
                    'schema_name': idx.schema_name,
                    'size_mb': idx.size_mb,
                }
                for idx in unused_indexes
            ],
            'missing_indexes': [
                {
                    'table_name': idx.table_name,
                    'schema_name': idx.schema_name,
                    'column_list': idx.column_list,
                    'recommendation': idx.recommendation,
                    'estimated_improvement_percent': idx.estimated_improvement_percent,
                }
                for idx in missing_indexes
            ],
            'wait_statistics': [
                {
                    'wait_type': w.wait_type,
                    'wait_count': w.wait_count,
                    'wait_time_ms': w.wait_time_ms,
                    'avg_wait_ms': w.avg_wait_ms,
                }
                for w in wait_statistics
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get live status for {db_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get live status: {str(e)}")


@router.get("/{run_id}/{metric_type}", dependencies=[AuthDep])
def get_live_metrics(run_id: int, metric_type: str):
    """Fetch specific metric type from a live metrics capture run.

    Metric types:
    - index_usage
    - unused_indexes
    - missing_indexes
    - slow_queries
    - blocking_sessions
    - wait_statistics
    - table_sizes
    """
    cursor = get_cursor()
    try:
        sql = """
            SELECT data_json, created_at
            FROM dmv_snapshots
            WHERE run_id = %s AND dmv_type = %s
            ORDER BY created_at DESC
            LIMIT 100
        """
        cursor.execute(sql, (run_id, metric_type))
        rows = cursor.fetchall()

        metrics = [
            {
                'data': json.loads(row[0]) if isinstance(row[0], str) else row[0],
                'captured_at': row[1].isoformat() if row[1] else None,
            }
            for row in rows
        ]

        return {
            'run_id': run_id,
            'metric_type': metric_type,
            'metrics': metrics,
            'total': len(metrics),
        }
    finally:
        cursor.close()
