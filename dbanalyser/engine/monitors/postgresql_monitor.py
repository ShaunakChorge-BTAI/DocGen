"""PostgreSQL-specific live monitoring using system catalogs and statistics views."""

from __future__ import annotations

import logging
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


class PostgreSQLMonitorAdapter(LiveMonitorAdapter):
    """Live performance metrics for PostgreSQL via pg_stat_* views."""

    def get_index_statistics(self, limit: int = 100) -> List[IndexStatistic]:
        """Fetch index usage stats from pg_stat_user_indexes."""
        sql = f"""
            SELECT
                i.relname AS index_name,
                t.relname AS table_name,
                n.nspname AS schema_name,
                COALESCE(s.idx_scan, 0) AS seeks,
                0 AS scans,
                0 AS lookups,
                COALESCE(s.idx_tup_read, 0) + COALESCE(s.idx_tup_fetch, 0) AS updates,
                COALESCE(s.last_idx_scan, NULL) AS last_used,
                CAST(pg_relation_size(i.oid) / 1024.0 / 1024.0 AS NUMERIC(10,2)) AS size_mb,
                ix.indisunique AS is_unique,
                ix.indisprimary AS is_primary_key
            FROM pg_stat_user_indexes s
            RIGHT JOIN pg_index ix ON s.indexrelid = ix.indexrelid
            INNER JOIN pg_class i ON ix.indexrelid = i.oid
            INNER JOIN pg_class t ON ix.indrelid = t.oid
            INNER JOIN pg_namespace n ON t.relnamespace = n.oid
            ORDER BY (COALESCE(s.idx_scan, 0)) DESC
            LIMIT {limit}
        """
        try:
            rows = self.driver.execute_query(sql, as_dict=False)
            return [
                IndexStatistic(
                    index_name=row[0],
                    table_name=row[1],
                    schema_name=row[2],
                    seeks=int(row[3]) if row[3] else 0,
                    scans=int(row[4]) if row[4] else 0,
                    lookups=int(row[5]) if row[5] else 0,
                    updates=int(row[6]) if row[6] else 0,
                    last_used=row[7],
                    size_mb=float(row[8]) if row[8] else None,
                    is_unique=bool(row[9]) if row[9] is not None else False,
                    is_primary_key=bool(row[10]) if row[10] is not None else False,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch index statistics: {e}")
            return []

    def get_unused_indexes(self, limit: int = 50) -> List[IndexStatistic]:
        """Fetch unused indexes with zero scans."""
        sql = f"""
            SELECT
                i.relname AS index_name,
                t.relname AS table_name,
                n.nspname AS schema_name,
                0 AS seeks,
                0 AS scans,
                0 AS lookups,
                0 AS updates,
                NULL AS last_used,
                CAST(pg_relation_size(i.oid) / 1024.0 / 1024.0 AS NUMERIC(10,2)) AS size_mb,
                ix.indisunique AS is_unique,
                ix.indisprimary AS is_primary_key
            FROM pg_index ix
            INNER JOIN pg_class i ON ix.indexrelid = i.oid
            INNER JOIN pg_class t ON ix.indrelid = t.oid
            INNER JOIN pg_namespace n ON t.relnamespace = n.oid
            WHERE NOT EXISTS (
                SELECT 1 FROM pg_stat_user_indexes s
                WHERE s.indexrelid = ix.indexrelid
                    AND (s.idx_scan > 0 OR s.idx_tup_read > 0)
            )
            AND ix.indisprimary = FALSE
            ORDER BY pg_relation_size(i.oid) DESC
            LIMIT {limit}
        """
        try:
            rows = self.driver.execute_query(sql, as_dict=False)
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
                    is_unique=bool(row[9]) if row[9] is not None else False,
                    is_primary_key=bool(row[10]) if row[10] is not None else False,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch unused indexes: {e}")
            return []

    def get_missing_indexes(self, limit: int = 20) -> List[MissingIndex]:
        """PostgreSQL does not have built-in missing index recommendations.

        Return empty list; users should run pgBadger or use pg_stat_statements
        to identify frequently used columns.
        """
        logger.info("PostgreSQL does not provide missing index recommendations via system views")
        return []

    def get_slow_queries(self, top_n: int = 50, duration_ms_min: int = 100) -> List[SlowQuery]:
        """Fetch slow queries from pg_stat_statements (requires extension)."""
        # Check if pg_stat_statements is available
        check_ext = "SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements' LIMIT 1"
        try:
            ext_result = self.driver.execute_query(check_ext, as_dict=False)
            if not ext_result:
                logger.warning("pg_stat_statements extension not installed")
                return []
        except Exception:
            pass

        sql = f"""
            SELECT
                query_hash,
                query,
                calls,
                mean_exec_time,
                total_exec_time,
                mean_exec_time,  -- Approximate for CPU
                total_exec_time,  -- Approximate for CPU
                rows / calls,
                0,  -- Writes not directly available
                COALESCE(max_exec_time, NULL) AS last_execution,
                NULL AS creation_time
            FROM (
                SELECT
                    CAST(md5(query) AS UUID) AS query_hash,
                    LEFT(query, 500) AS query,
                    calls,
                    mean_exec_time,
                    total_exec_time,
                    rows,
                    max_exec_time
                FROM pg_stat_statements
                WHERE mean_exec_time >= {duration_ms_min}
                ORDER BY total_exec_time DESC
                LIMIT {top_n}
            ) sub
        """
        try:
            rows = self.driver.execute_query(sql, as_dict=False)
            return [
                SlowQuery(
                    query_hash=str(row[0]) if row[0] else "",
                    query_text=row[1] or "",
                    execution_count=int(row[2]) if row[2] else 0,
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
        """Fetch blocking session chains from pg_stat_activity."""
        sql = """
            SELECT
                pid AS session_id,
                datname AS database_name,
                usename AS user_name,
                application_name AS program_name,
                client_hostname AS host_name,
                backend_start AS login_time,
                state AS status,
                wait_event AS wait_type,
                wait_event_type,
                EXTRACT(EPOCH FROM (NOW() - query_start)) * 1000 AS wait_duration_ms,
                pg_blocking_pids(pid)[1]::INT AS blocking_session_id,
                state_change,
                NULL AS open_transaction_count
            FROM pg_stat_activity
            WHERE (
                ARRAY_LENGTH(pg_blocking_pids(pid), 1) > 0
                OR EXISTS (
                    SELECT 1 FROM pg_stat_activity a2
                    WHERE pid = ANY(pg_blocking_pids(a2.pid))
                )
            )
            AND pid != pg_backend_pid()
            ORDER BY COALESCE(pg_blocking_pids(pid)[1], 0), pid
        """
        try:
            rows = self.driver.execute_query(sql, as_dict=False)
            return [
                BlockingSession(
                    session_id=int(row[0]),
                    database_name=row[1] or "",
                    user_name=row[2] or "",
                    program_name=row[3],
                    host_name=str(row[4]) if row[4] else None,
                    start_time=row[5],
                    status=row[6] or "",
                    wait_type=row[7],
                    wait_duration_ms=int(row[9]) if row[9] else 0,
                    blocking_session_id=int(row[10]) if row[10] else None,
                    last_command=row[11],
                    open_transaction_count=0,  # Not directly available in PostgreSQL
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch blocking sessions: {e}")
            return []

    def get_wait_statistics(self, limit: int = 50) -> List[WaitStatistic]:
        """PostgreSQL does not provide wait statistics like SQL Server.

        Return empty list or basic I/O stats approximation.
        """
        logger.info("PostgreSQL wait statistics not available via system views")
        return []

    def get_table_sizes(self, limit: int = 100) -> List[TableSize]:
        """Fetch table sizes from pg_tables and pg_stat_user_tables."""
        sql = f"""
            SELECT
                t.tablename AS table_name,
                n.nspname AS schema_name,
                s.n_live_tup AS row_count,
                CAST(pg_total_relation_size(t.schemaname||'.'||t.tablename) / 1024.0 / 1024.0 AS NUMERIC(10,2)) AS reserved_mb,
                CAST(pg_relation_size(t.schemaname||'.'||t.tablename) / 1024.0 / 1024.0 AS NUMERIC(10,2)) AS used_mb,
                NULL AS unused_mb,
                CAST(pg_relation_size(t.schemaname||'.'||t.tablename) / 1024.0 / 1024.0 AS NUMERIC(10,2)) AS data_mb,
                CAST((pg_total_relation_size(t.schemaname||'.'||t.tablename) - pg_relation_size(t.schemaname||'.'||t.tablename)) / 1024.0 / 1024.0 AS NUMERIC(10,2)) AS index_mb,
                NULL AS lob_mb,
                NULL AS partition_count
            FROM pg_tables t
            LEFT JOIN pg_stat_user_tables s ON t.tablename = s.relname AND t.schemaname = s.schemaname
            LEFT JOIN pg_namespace n ON n.nspname = t.schemaname
            WHERE t.schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_total_relation_size(t.schemaname||'.'||t.tablename) DESC
            LIMIT {limit}
        """
        try:
            rows = self.driver.execute_query(sql, as_dict=False)
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
                    partition_count=None,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch table sizes: {e}")
            return []
