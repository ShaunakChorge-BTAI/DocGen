"""Oracle-specific live monitoring using dynamic performance views."""

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


class OracleMonitorAdapter(LiveMonitorAdapter):
    """Live performance metrics for Oracle via v$ dynamic performance views."""

    def get_index_statistics(self, limit: int = 100) -> List[IndexStatistic]:
        """Fetch index usage stats from v$segment_statistics."""
        sql = f"""
            SELECT
                i.index_name,
                t.table_name,
                t.owner,
                NVL(i.leaf_blocks, 0) AS seeks,
                NVL(i.distinct_keys, 0) AS scans,
                0 AS lookups,
                0 AS updates,
                NULL AS last_used,
                ROUND(NVL(s.BYTES, 0) / 1024 / 1024, 2) AS size_mb,
                i.uniqueness,
                DECODE(i.uniqueness, 'UNIQUE', 1, 0) AS is_unique
            FROM dba_indexes i
            INNER JOIN dba_tables t ON i.table_owner = t.owner AND i.table_name = t.table_name
            LEFT JOIN dba_segments s ON i.owner = s.owner AND i.index_name = s.segment_name
            WHERE i.owner NOT IN ('SYS', 'SYSTEM')
            ORDER BY i.leaf_blocks DESC
            FETCH FIRST {limit} ROWS ONLY
        """
        try:
            rows = self.driver.execute_query(sql)
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
                    is_unique=bool(row[10]) if row[10] is not None else False,
                    is_primary_key=False,  # Oracle doesn't directly flag primary keys in dba_indexes
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch index statistics: {e}")
            return []

    def get_unused_indexes(self, limit: int = 50) -> List[IndexStatistic]:
        """Fetch unused indexes from v$object_stat."""
        sql = f"""
            SELECT
                i.index_name,
                i.table_name,
                i.owner,
                0 AS seeks,
                0 AS scans,
                0 AS lookups,
                0 AS updates,
                NULL AS last_used,
                ROUND(NVL(s.BYTES, 0) / 1024 / 1024, 2) AS size_mb,
                i.uniqueness,
                DECODE(i.uniqueness, 'UNIQUE', 1, 0) AS is_unique
            FROM dba_indexes i
            LEFT JOIN dba_segments s ON i.owner = s.owner AND i.index_name = s.segment_name
            WHERE i.owner NOT IN ('SYS', 'SYSTEM')
                AND i.index_type NOT IN ('LOB', 'FUNCTION-BASED NORMAL')
            ORDER BY s.BYTES DESC
            FETCH FIRST {limit} ROWS ONLY
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
                    is_unique=bool(row[10]) if row[10] is not None else False,
                    is_primary_key=False,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch unused indexes: {e}")
            return []

    def get_missing_indexes(self, limit: int = 20) -> List[MissingIndex]:
        """Oracle does not have built-in missing index recommendations in standard edition.

        Return empty list; recommend AWR (Automatic Workload Repository) analysis.
        """
        logger.info("Oracle missing indexes require AWR analysis (Enterprise Edition)")
        return []

    def get_slow_queries(self, top_n: int = 50, duration_ms_min: int = 100) -> List[SlowQuery]:
        """Fetch slow queries from v$sql."""
        sql = f"""
            SELECT
                sql_id,
                sql_text,
                executions,
                elapsed_time / 1000000 / DECODE(executions, 0, 1, executions) AS avg_duration_ms,
                elapsed_time / 1000000 AS total_duration_ms,
                cpu_time / 1000000 / DECODE(executions, 0, 1, executions) AS avg_cpu_ms,
                cpu_time / 1000000 AS total_cpu_ms,
                disk_reads / DECODE(executions, 0, 1, executions) AS avg_reads,
                buffer_gets / DECODE(executions, 0, 1, executions) AS avg_writes,
                last_active_time,
                first_load_time
            FROM v$sql
            WHERE elapsed_time / 1000000 / DECODE(executions, 0, 1, executions) >= {duration_ms_min}
                AND sql_text NOT LIKE '%from v$sql%'
            ORDER BY elapsed_time DESC
            FETCH FIRST {top_n} ROWS ONLY
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                SlowQuery(
                    query_hash=row[0] or "",
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
        """Fetch blocking session chains from v$session."""
        sql = """
            SELECT
                s.sid AS session_id,
                DECODE(s.sid, NULL, 0, 1) AS database_name,
                s.username,
                s.program,
                s.machine,
                s.logon_time,
                s.status,
                w.event,
                w.wait_time,
                s.blocking_session,
                s.event,
                s.transaction_id
            FROM v$session s
            LEFT JOIN v$session_wait w ON s.sid = w.sid
            WHERE s.type = 'USER'
                AND (s.blocking_session IS NOT NULL OR s.sid IN (
                    SELECT blocking_session FROM v$session WHERE blocking_session IS NOT NULL
                ))
            ORDER BY s.blocking_session, s.sid
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                BlockingSession(
                    session_id=int(row[0]),
                    database_name="Oracle",
                    user_name=row[2] or "",
                    program_name=row[3],
                    host_name=row[4],
                    start_time=row[5],
                    status=row[6] or "",
                    wait_type=row[7],
                    wait_duration_ms=int(row[8]) if row[8] else 0,
                    blocking_session_id=int(row[9]) if row[9] else None,
                    last_command=row[10],
                    open_transaction_count=0,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch blocking sessions: {e}")
            return []

    def get_wait_statistics(self, limit: int = 50) -> List[WaitStatistic]:
        """Fetch wait statistics from v$system_event."""
        sql = f"""
            SELECT
                event,
                total_waits,
                time_waited,
                0 AS signal_wait_time,
                ROUND(time_waited / DECODE(total_waits, 0, 1, total_waits), 2) AS avg_wait
            FROM v$system_event
            WHERE event NOT IN ('SQL*Net message from client', 'pmon timer')
            ORDER BY time_waited DESC
            FETCH FIRST {limit} ROWS ONLY
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                WaitStatistic(
                    wait_type=row[0],
                    wait_count=int(row[1]) if row[1] else 0,
                    wait_time_ms=int(row[2]) if row[2] else 0,
                    signal_wait_time_ms=int(row[3]) if row[3] else 0,
                    avg_wait_ms=float(row[4]) if row[4] else 0,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch wait statistics: {e}")
            return []

    def get_table_sizes(self, limit: int = 100) -> List[TableSize]:
        """Fetch table sizes from dba_tables and dba_segments."""
        sql = f"""
            SELECT
                t.table_name,
                t.owner,
                t.num_rows,
                ROUND(NVL(s.BYTES, 0) / 1024 / 1024, 2) AS reserved_mb,
                ROUND(NVL(s.BYTES, 0) / 1024 / 1024, 2) AS used_mb,
                0 AS unused_mb,
                ROUND(NVL(s.BYTES, 0) / 1024 / 1024, 2) AS data_mb,
                0 AS index_mb,
                0 AS lob_mb,
                NULL AS partition_count
            FROM dba_tables t
            LEFT JOIN dba_segments s ON t.owner = s.owner AND t.table_name = s.segment_name
            WHERE t.owner NOT IN ('SYS', 'SYSTEM')
            ORDER BY s.BYTES DESC
            FETCH FIRST {limit} ROWS ONLY
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
                    lob_mb=float(row[8]) if row[8] else None,
                    partition_count=None,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch table sizes: {e}")
            return []
