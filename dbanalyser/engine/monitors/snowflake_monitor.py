"""Snowflake-specific live monitoring using ACCOUNT_USAGE schema."""

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


class SnowflakeMonitorAdapter(LiveMonitorAdapter):
    """Live performance metrics for Snowflake via ACCOUNT_USAGE schema."""

    def get_index_statistics(self, limit: int = 100) -> List[IndexStatistic]:
        """Snowflake does not have traditional indexes.

        Snowflake automatically clusters data; return empty list.
        """
        logger.info("Snowflake uses automatic clustering; traditional indexes not applicable")
        return []

    def get_unused_indexes(self, limit: int = 50) -> List[IndexStatistic]:
        """Snowflake does not have traditional indexes."""
        logger.info("Snowflake uses automatic clustering; traditional indexes not applicable")
        return []

    def get_missing_indexes(self, limit: int = 20) -> List[MissingIndex]:
        """Snowflake does not provide missing index recommendations.

        Snowflake uses automatic clustering and micro-partitioning.
        """
        logger.info("Snowflake uses automatic clustering; index recommendations not applicable")
        return []

    def get_slow_queries(self, top_n: int = 50, duration_ms_min: int = 100) -> List[SlowQuery]:
        """Fetch slow queries from ACCOUNT_USAGE.QUERY_HISTORY."""
        sql = f"""
            SELECT
                query_id,
                LEFT(query_text, 500) AS query_text,
                execution_count,
                AVG(total_elapsed_time) AS avg_duration_ms,
                SUM(total_elapsed_time) AS total_duration_ms,
                AVG(compilation_time) AS avg_cpu_ms,
                SUM(compilation_time) AS total_cpu_ms,
                0 AS avg_reads,
                0 AS avg_writes,
                MAX(end_time) AS last_execution,
                MIN(start_time) AS creation_time
            FROM snowflake.account_usage.query_history
            WHERE query_status = 'SUCCESS'
                AND total_elapsed_time >= {duration_ms_min}
                AND query_text NOT LIKE '%from account_usage%'
            GROUP BY query_id, query_text, execution_count
            ORDER BY total_elapsed_time DESC
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
        """Snowflake does not expose session blocking information.

        Snowflake handles locking automatically with MVCC; return empty list.
        """
        logger.info("Snowflake uses MVCC; explicit session blocking not exposed")
        return []

    def get_wait_statistics(self, limit: int = 50) -> List[WaitStatistic]:
        """Snowflake does not expose wait statistics like traditional databases.

        Return empty list; monitor warehouse queue times instead.
        """
        logger.info("Snowflake does not expose wait statistics; monitor warehouse metrics instead")
        return []

    def get_table_sizes(self, limit: int = 100) -> List[TableSize]:
        """Fetch table sizes from INFORMATION_SCHEMA.TABLES."""
        sql = f"""
            SELECT
                table_name,
                table_schema,
                row_count,
                ROUND(bytes / 1024 / 1024, 2) AS reserved_mb,
                ROUND(bytes / 1024 / 1024, 2) AS used_mb,
                0 AS unused_mb,
                ROUND(bytes / 1024 / 1024, 2) AS data_mb,
                0 AS index_mb,
                0 AS lob_mb,
                NULL AS partition_count
            FROM snowflake.account_usage.table_storage_metrics
            WHERE deleted_on IS NULL
            ORDER BY bytes DESC
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
                    lob_mb=float(row[8]) if row[8] else None,
                    partition_count=None,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch table sizes: {e}")
            return []
