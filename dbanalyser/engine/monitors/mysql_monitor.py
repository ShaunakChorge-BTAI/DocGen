"""MySQL-specific live monitoring using performance_schema and information_schema."""

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


class MySQLMonitorAdapter(LiveMonitorAdapter):
    """Live performance metrics for MySQL via performance_schema."""

    def get_index_statistics(self, limit: int = 100) -> List[IndexStatistic]:
        """Fetch index usage stats from performance_schema.table_io_waits_summary_by_index_usage."""
        sql = f"""
            SELECT
                i.index_name,
                t.table_name,
                t.table_schema,
                COALESCE(s.select_count, 0) AS seeks,
                0 AS scans,
                0 AS lookups,
                COALESCE(s.update_count + s.insert_count + s.delete_count, 0) AS updates,
                COALESCE(s.last_write, NULL) AS last_used,
                ROUND(((SELECT COALESCE(SUM(stat_value), 0)
                        FROM performance_schema.table_io_waits_summary_by_index_usage
                        WHERE object_name = i.index_name
                        AND object_schema = t.table_schema) / 1024 / 1024), 2) AS size_mb,
                CASE WHEN i.non_unique = 0 THEN 1 ELSE 0 END AS is_unique,
                CASE WHEN i.index_name = 'PRIMARY' THEN 1 ELSE 0 END AS is_primary_key
            FROM information_schema.statistics i
            LEFT JOIN performance_schema.table_io_waits_summary_by_index_usage s
                ON i.index_name = s.index_name
                AND i.table_name = s.object_name
                AND i.table_schema = s.object_schema
            INNER JOIN information_schema.tables t ON i.table_schema = t.table_schema
                AND i.table_name = t.table_name
            WHERE i.table_schema NOT IN ('mysql', 'performance_schema', 'information_schema')
                AND i.index_name != 'PRIMARY'
            GROUP BY i.index_name, i.table_name, i.table_schema
            ORDER BY COALESCE(s.select_count, 0) DESC
            LIMIT {limit}
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
                    is_unique=bool(row[9]) if row[9] is not None else False,
                    is_primary_key=bool(row[10]) if row[10] is not None else False,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch index statistics: {e}")
            return []

    def get_unused_indexes(self, limit: int = 50) -> List[IndexStatistic]:
        """Fetch unused indexes with zero reads/writes."""
        sql = f"""
            SELECT
                i.index_name,
                i.table_name,
                i.table_schema,
                0 AS seeks,
                0 AS scans,
                0 AS lookups,
                0 AS updates,
                NULL AS last_used,
                NULL AS size_mb,
                CASE WHEN i.non_unique = 0 THEN 1 ELSE 0 END AS is_unique,
                CASE WHEN i.index_name = 'PRIMARY' THEN 1 ELSE 0 END AS is_primary_key
            FROM information_schema.statistics i
            WHERE i.table_schema NOT IN ('mysql', 'performance_schema', 'information_schema')
                AND i.index_name != 'PRIMARY'
                AND NOT EXISTS (
                    SELECT 1 FROM performance_schema.table_io_waits_summary_by_index_usage s
                    WHERE s.index_name = i.index_name
                        AND s.object_name = i.table_name
                        AND s.object_schema = i.table_schema
                        AND (s.select_count > 0 OR s.update_count > 0 OR s.insert_count > 0 OR s.delete_count > 0)
                )
            LIMIT {limit}
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
                    size_mb=None,
                    is_unique=bool(row[9]) if row[9] is not None else False,
                    is_primary_key=bool(row[10]) if row[10] is not None else False,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch unused indexes: {e}")
            return []

    def get_missing_indexes(self, limit: int = 20) -> List[MissingIndex]:
        """MySQL does not provide missing index recommendations.

        Return empty list; users should analyze slow query log or use Percona tools.
        """
        logger.info("MySQL does not provide missing index recommendations via performance_schema")
        return []

    def get_slow_queries(self, top_n: int = 50, duration_ms_min: int = 100) -> List[SlowQuery]:
        """Fetch slow queries from performance_schema.events_statements_summary_by_digest."""
        sql = f"""
            SELECT
                DIGEST,
                DIGEST_TEXT,
                COUNT_STAR,
                AVG_TIMER_WAIT / 1000000000000 AS avg_duration_ms,
                SUM_TIMER_WAIT / 1000000000000 AS total_duration_ms,
                AVG_TIMER_WAIT / 1000000000000 AS avg_cpu_ms,
                SUM_TIMER_WAIT / 1000000000000 AS total_cpu_ms,
                0 AS avg_reads,
                0 AS avg_writes,
                FIRST_SEEN,
                LAST_SEEN
            FROM performance_schema.events_statements_summary_by_digest
            WHERE AVG_TIMER_WAIT / 1000000000000 >= {duration_ms_min}
                AND DIGEST_TEXT NOT LIKE '%performance_schema%'
            ORDER BY SUM_TIMER_WAIT DESC
            LIMIT {top_n}
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
        """Fetch blocking session chains from information_schema.processlist."""
        sql = """
            SELECT
                p.id AS session_id,
                p.db AS database_name,
                p.user AS user_name,
                p.command,
                p.host,
                p.time AS start_time,
                p.state,
                NULL AS wait_type,
                COALESCE(p.time, 0) * 1000 AS wait_duration_ms,
                NULL AS blocking_session_id,
                p.info,
                0 AS open_transaction_count
            FROM information_schema.processlist p
            WHERE p.command != 'Sleep'
                AND p.user NOT IN ('system user', 'root')
            ORDER BY p.id
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
                    blocking_session_id=None,
                    last_command=row[10],
                    open_transaction_count=int(row[11]) if row[11] else 0,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch blocking sessions: {e}")
            return []

    def get_wait_statistics(self, limit: int = 50) -> List[WaitStatistic]:
        """Fetch wait statistics from performance_schema.events_waits_summary_global_by_event_name."""
        sql = f"""
            SELECT
                event_name,
                count_star,
                sum_timer_wait / 1000000000000 AS wait_time_ms,
                0 AS signal_wait_time,
                (sum_timer_wait / 1000000000000) / COALESCE(count_star, 1) AS avg_wait_ms
            FROM performance_schema.events_waits_summary_global_by_event_name
            WHERE count_star > 0
                AND event_name NOT LIKE '%idle%'
            ORDER BY sum_timer_wait DESC
            LIMIT {limit}
        """
        try:
            rows = self.driver.execute_query(sql)
            return [
                WaitStatistic(
                    wait_type=row[0],
                    wait_count=int(row[1]) if row[1] else 0,
                    wait_time_ms=int(row[2]) if row[2] else 0,
                    signal_wait_time_ms=0,
                    avg_wait_ms=float(row[4]) if row[4] else 0,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch wait statistics: {e}")
            return []

    def get_table_sizes(self, limit: int = 100) -> List[TableSize]:
        """Fetch table sizes from information_schema.tables."""
        sql = f"""
            SELECT
                t.table_name,
                t.table_schema,
                t.table_rows,
                ROUND((t.data_length + t.index_length) / 1024 / 1024, 2) AS reserved_mb,
                ROUND((t.data_length + t.index_length) / 1024 / 1024, 2) AS used_mb,
                0 AS unused_mb,
                ROUND(t.data_length / 1024 / 1024, 2) AS data_mb,
                ROUND(t.index_length / 1024 / 1024, 2) AS index_mb,
                NULL AS lob_mb,
                NULL AS partition_count
            FROM information_schema.tables t
            WHERE t.table_schema NOT IN ('mysql', 'performance_schema', 'information_schema', 'sys')
            ORDER BY (t.data_length + t.index_length) DESC
            LIMIT {limit}
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
                    partition_count=None,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch table sizes: {e}")
            return []
