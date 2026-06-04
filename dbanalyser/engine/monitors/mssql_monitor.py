"""MSSQL-specific live monitoring using Dynamic Management Views (DMVs)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from dbanalyser.engine.live_monitor import (
    LiveMonitorAdapter,
    IndexStatistic,
    MissingIndex,
    SlowQuery,
    BlockingSession,
    WaitStatistic,
    TableSize,
)

logger = logging.getLogger(__name__)


class MSSQLMonitorAdapter(LiveMonitorAdapter):
    """Live performance metrics for SQL Server via DMVs."""

    def get_index_statistics(self, limit: int = 100) -> List[IndexStatistic]:
        """Fetch index usage stats from sys.dm_db_index_usage_stats."""
        sql = f"""
            SELECT TOP {limit}
                i.name AS index_name,
                OBJECT_NAME(s.object_id) AS table_name,
                SCHEMA_NAME(t.schema_id) AS schema_name,
                ISNULL(s.user_seeks, 0) AS seeks,
                ISNULL(s.user_scans, 0) AS scans,
                ISNULL(s.user_lookups, 0) AS lookups,
                ISNULL(s.user_updates, 0) AS updates,
                ISNULL(s.last_user_seek, s.last_user_scan) AS last_used,
                CAST(
                    (8 * SUM(p.used_page_count)) / 1024.0 AS NUMERIC(10,2)
                ) AS size_mb,
                i.is_unique,
                i.is_primary_key
            FROM sys.dm_db_index_usage_stats s
            INNER JOIN sys.indexes i ON s.object_id = i.object_id
                AND s.index_id = i.index_id
            INNER JOIN sys.objects t ON s.object_id = t.object_id
            INNER JOIN sys.allocation_units p ON i.object_id = p.container_id
            WHERE database_id = DB_ID()
                AND i.index_id > 0  -- Skip heaps
            GROUP BY i.name, s.object_id, t.schema_id, s.user_seeks, s.user_scans,
                     s.user_lookups, s.user_updates, s.last_user_seek, s.last_user_scan,
                     i.is_unique, i.is_primary_key
            ORDER BY (s.user_seeks + s.user_scans + s.user_lookups) DESC
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                IndexStatistic(
                    index_name=row[0],
                    table_name=row[1],
                    schema_name=row[2],
                    seeks=int(row[3]),
                    scans=int(row[4]),
                    lookups=int(row[5]),
                    updates=int(row[6]),
                    last_used=row[7],
                    size_mb=float(row[8]) if row[8] else None,
                    is_unique=bool(row[9]),
                    is_primary_key=bool(row[10]),
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch index statistics: {e}")
            return []

    def get_unused_indexes(self, limit: int = 50) -> List[IndexStatistic]:
        """Fetch indexes with zero usage."""
        sql = f"""
            SELECT TOP {limit}
                i.name AS index_name,
                OBJECT_NAME(i.object_id) AS table_name,
                SCHEMA_NAME(t.schema_id) AS schema_name,
                0 AS seeks,
                0 AS scans,
                0 AS lookups,
                0 AS updates,
                NULL AS last_used,
                CAST(
                    (8 * SUM(p.used_page_count)) / 1024.0 AS NUMERIC(10,2)
                ) AS size_mb,
                i.is_unique,
                i.is_primary_key
            FROM sys.indexes i
            INNER JOIN sys.objects t ON i.object_id = t.object_id
            INNER JOIN sys.allocation_units p ON i.object_id = p.container_id
            WHERE NOT EXISTS (
                SELECT 1 FROM sys.dm_db_index_usage_stats s
                WHERE s.object_id = i.object_id
                    AND s.index_id = i.index_id
                    AND s.database_id = DB_ID()
            )
            AND i.index_id > 0
            AND i.is_primary_key = 0
            GROUP BY i.name, i.object_id, t.schema_id, i.is_unique, i.is_primary_key
            ORDER BY SUM(p.used_page_count) DESC
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                IndexStatistic(
                    index_name=row[0],
                    table_name=row[1],
                    schema_name=row[2],
                    seeks=0,
                    scans=0,
                    lookups=0,
                    updates=0,
                    last_used=None,
                    size_mb=float(row[8]) if row[8] else None,
                    is_unique=bool(row[9]),
                    is_primary_key=bool(row[10]),
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch unused indexes: {e}")
            return []

    def get_missing_indexes(self, limit: int = 20) -> List[MissingIndex]:
        """Fetch missing index recommendations from sys.dm_db_missing_index_*."""
        sql = f"""
            SELECT TOP {limit}
                CONVERT(DECIMAL(18,2), migs.user_seeks * migs.avg_total_user_cost * (migs.avg_user_impact * 0.01)) AS improvement,
                mid.equality_columns,
                mid.included_columns,
                OBJECT_NAME(mid.object_id) AS table_name,
                SCHEMA_NAME(OBJECT_ID(mid.statement)) AS schema_name,
                migs.user_seeks,
                migs.user_scans
            FROM sys.dm_db_missing_index_details mid
            INNER JOIN sys.dm_db_missing_index_groups mig
                ON mid.index_handle = mig.index_handle
            INNER JOIN sys.dm_db_missing_index_groups_stats migs
                ON mig.index_group_id = migs.group_id
                AND mig.index_handle = migs.index_handle
            WHERE database_id = DB_ID()
            ORDER BY improvement DESC
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                MissingIndex(
                    table_name=row[3],
                    schema_name=row[4],
                    column_list=row[1] or "",
                    include_column_list=row[2],
                    estimated_improvement_percent=float(row[0]) if row[0] else 0,
                    user_seeks=int(row[5]),
                    user_scans=int(row[6]),
                    recommendation=f"CREATE INDEX idx_{row[3]}_missing ON {row[4]}.{row[3]} ({row[1] or ''})" +
                                   (f" INCLUDE ({row[2]})" if row[2] else ""),
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch missing indexes: {e}")
            return []

    def get_slow_queries(self, top_n: int = 50, duration_ms_min: int = 100) -> List[SlowQuery]:
        """Fetch slow queries from sys.dm_exec_query_stats."""
        sql = f"""
            SELECT TOP {top_n}
                qs.plan_handle,
                qt.text,
                qs.execution_count,
                qs.total_elapsed_time / 1000.0 / qs.execution_count AS avg_duration_ms,
                qs.total_elapsed_time / 1000.0 AS total_duration_ms,
                qs.total_worker_time / 1000.0 / qs.execution_count AS avg_cpu_ms,
                qs.total_worker_time / 1000.0 AS total_cpu_ms,
                qs.total_logical_reads / qs.execution_count AS avg_reads,
                qs.total_logical_writes / qs.execution_count AS avg_writes,
                qs.last_execution_time,
                qs.creation_time,
                qs.query_hash
            FROM sys.dm_exec_query_stats qs
            CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
            WHERE qs.total_elapsed_time / 1000.0 / qs.execution_count >= {duration_ms_min}
            ORDER BY qs.total_elapsed_time DESC
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                SlowQuery(
                    query_hash=str(row[11]) if row[11] else "",
                    query_text=row[1] or "",
                    execution_count=int(row[2]),
                    avg_duration_ms=float(row[3]) if row[3] else 0,
                    total_duration_ms=float(row[4]) if row[4] else 0,
                    avg_cpu_ms=float(row[5]) if row[5] else 0,
                    total_cpu_ms=float(row[6]) if row[6] else 0,
                    avg_reads=int(row[7]) if row[7] else 0,
                    avg_writes=int(row[8]) if row[8] else 0,
                    last_execution=row[9],
                    creation_time=row[10],
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch slow queries: {e}")
            return []

    def get_blocking_sessions(self) -> List[BlockingSession]:
        """Fetch blocking session chains from sys.dm_exec_requests."""
        sql = """
            SELECT
                r.session_id,
                DB_NAME(r.database_id) AS database_name,
                s.login_name,
                s.program_name,
                s.host_name,
                s.login_time,
                r.status,
                r.wait_type,
                r.wait_time,
                r.blocking_session_id,
                r.last_wait_type,
                s.open_transaction_count
            FROM sys.dm_exec_requests r
            INNER JOIN sys.dm_exec_sessions s ON r.session_id = s.session_id
            WHERE r.session_id > 50  -- Exclude system sessions
                AND (r.blocking_session_id > 0 OR EXISTS (
                    SELECT 1 FROM sys.dm_exec_requests r2
                    WHERE r2.blocking_session_id = r.session_id
                ))
            ORDER BY r.blocking_session_id, r.session_id
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                BlockingSession(
                    session_id=int(row[0]),
                    database_name=row[1] or "",
                    user_name=row[2] or "",
                    program_name=row[3],
                    host_name=row[4],
                    start_time=row[5],
                    status=row[6] or "",
                    wait_type=row[7],
                    wait_duration_ms=int(row[8]) if row[8] else 0,
                    blocking_session_id=int(row[9]) if row[9] and row[9] > 0 else None,
                    last_command=row[10],
                    open_transaction_count=int(row[11]) if row[11] else 0,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch blocking sessions: {e}")
            return []

    def get_wait_statistics(self, limit: int = 50) -> List[WaitStatistic]:
        """Fetch wait statistics from sys.dm_os_wait_stats."""
        sql = f"""
            SELECT TOP {limit}
                wait_type,
                waiting_tasks_count,
                wait_time_ms,
                signal_wait_time_ms,
                CAST(wait_time_ms AS FLOAT) / CAST(waiting_tasks_count AS FLOAT) AS avg_wait_ms
            FROM sys.dm_os_wait_stats
            WHERE wait_type NOT IN (
                'SLEEP_TASK', 'LAZYWRITER_SLEEP', 'SQLTRACE_INCREMENTAL_FLUSH_SLEEP',
                'BROKER_TO_FLUSH', 'XE_TIMER_EVENT', 'REQUEST_FOR_DEADLOCK_SEARCH'
            )
            ORDER BY wait_time_ms DESC
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                WaitStatistic(
                    wait_type=row[0],
                    wait_count=int(row[1]),
                    wait_time_ms=int(row[2]),
                    signal_wait_time_ms=int(row[3]) if row[3] else 0,
                    avg_wait_ms=float(row[4]) if row[4] else 0,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch wait statistics: {e}")
            return []

    def get_table_sizes(self, limit: int = 100) -> List[TableSize]:
        """Fetch table sizes from sys.dm_db_partition_stats."""
        sql = f"""
            SELECT TOP {limit}
                OBJECT_NAME(p.object_id) AS table_name,
                SCHEMA_NAME(o.schema_id) AS schema_name,
                SUM(p.rows) AS row_count,
                CAST(SUM(p.reserved_page_count) * 8.0 / 1024 AS NUMERIC(10,2)) AS reserved_mb,
                CAST(SUM(p.used_page_count) * 8.0 / 1024 AS NUMERIC(10,2)) AS used_mb,
                CAST(SUM(p.reserved_page_count - p.used_page_count) * 8.0 / 1024 AS NUMERIC(10,2)) AS unused_mb,
                CAST(SUM(CASE WHEN p.index_id <= 1 THEN p.used_page_count ELSE 0 END) * 8.0 / 1024 AS NUMERIC(10,2)) AS data_mb,
                CAST(SUM(CASE WHEN p.index_id > 1 THEN p.used_page_count ELSE 0 END) * 8.0 / 1024 AS NUMERIC(10,2)) AS index_mb,
                NULL AS lob_mb,
                COUNT(DISTINCT p.partition_number) AS partition_count
            FROM sys.dm_db_partition_stats p
            INNER JOIN sys.objects o ON p.object_id = o.object_id
            WHERE p.index_id < 2  -- Clustered index only
                AND o.type = 'U'  -- User tables only
            GROUP BY p.object_id, o.schema_id
            ORDER BY SUM(p.used_page_count) DESC
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                TableSize(
                    table_name=row[0],
                    schema_name=row[1],
                    row_count=int(row[2]) if row[2] else 0,
                    reserved_mb=float(row[3]) if row[3] else None,
                    used_mb=float(row[4]) if row[4] else None,
                    unused_mb=float(row[5]) if row[5] else None,
                    data_mb=float(row[6]) if row[6] else None,
                    index_mb=float(row[7]) if row[7] else None,
                    lob_mb=None,
                    partition_count=int(row[9]) if row[9] else 1,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch table sizes: {e}")
            return []
