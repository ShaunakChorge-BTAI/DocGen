"""Live monitoring abstraction layer for capturing real-time performance metrics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

# ── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class IndexStatistic:
    """Index usage and performance statistics."""
    index_name: str
    table_name: str
    schema_name: str
    seeks: int
    scans: int
    lookups: int
    updates: int
    last_used: Optional[datetime]
    size_mb: Optional[float]
    is_unique: bool
    is_primary_key: bool


@dataclass
class MissingIndex:
    """Recommended missing index with improvement estimate."""
    table_name: str
    schema_name: str
    column_list: str
    include_column_list: Optional[str]
    estimated_improvement_percent: float
    user_seeks: int
    user_scans: int
    recommendation: str


@dataclass
class SlowQuery:
    """Slow query with execution metrics."""
    query_hash: str
    query_text: str
    execution_count: int
    avg_duration_ms: float
    total_duration_ms: float
    avg_cpu_ms: float
    total_cpu_ms: float
    avg_reads: int
    avg_writes: int
    last_execution: Optional[datetime]
    creation_time: Optional[datetime]


@dataclass
class BlockingSession:
    """Active session blocking chain."""
    session_id: int
    database_name: str
    user_name: str
    program_name: Optional[str]
    host_name: Optional[str]
    start_time: datetime
    status: str
    wait_type: Optional[str]
    wait_duration_ms: int
    blocking_session_id: Optional[int]
    last_command: Optional[str]
    open_transaction_count: int


@dataclass
class WaitStatistic:
    """Database wait time statistics."""
    wait_type: str
    wait_count: int
    wait_time_ms: int
    signal_wait_time_ms: int
    avg_wait_ms: float


@dataclass
class TableSize:
    """Table row count and disk usage."""
    table_name: str
    schema_name: str
    row_count: int
    reserved_mb: Optional[float]
    used_mb: Optional[float]
    unused_mb: Optional[float]
    data_mb: Optional[float]
    index_mb: Optional[float]
    lob_mb: Optional[float]
    partition_count: int


# ── Abstract Monitor Interface ─────────────────────────────────────────────────

class LiveMonitorAdapter(ABC):
    """Abstract base class for capturing live performance metrics from any database type.

    Each database type implements these methods using appropriate system views/tables:
    - MSSQL: DMVs (sys.dm_exec_requests, sys.dm_exec_sql_text, etc.)
    - Oracle: v$ dynamic performance views (v$session, v$sql, etc.)
    - PostgreSQL: pg_stat_* catalog views (pg_stat_statements, pg_stat_activity, etc.)
    - MySQL: performance_schema and information_schema
    - Snowflake: QUERY_HISTORY, ACCOUNT_USAGE schema
    """

    def __init__(self, driver):
        """Initialize monitor with database driver instance.

        Args:
            driver: DatabaseDriver instance (test_connection already passed at this point)
        """
        self.driver = driver

    @abstractmethod
    def get_index_statistics(self, limit: int = 100) -> List[IndexStatistic]:
        """Fetch index usage and performance statistics.

        Returns top N indexes by activity (seeks + scans + lookups) across all tables.
        Includes: seeks, scans, lookups, updates, last_used timestamp, size, uniqueness, PK status.

        Args:
            limit: Maximum number of indexes to return

        Returns:
            List of IndexStatistic objects, sorted by activity (descending)
        """
        pass

    @abstractmethod
    def get_unused_indexes(self, limit: int = 50) -> List[IndexStatistic]:
        """Fetch indexes with zero or minimal usage.

        Identifies potentially unused indexes that can be dropped to free space.

        Args:
            limit: Maximum number of unused indexes to return

        Returns:
            List of IndexStatistic objects with seeks=0, scans=0, lookups=0
        """
        pass

    @abstractmethod
    def get_missing_indexes(self, limit: int = 20) -> List[MissingIndex]:
        """Fetch recommended missing indexes with improvement estimates.

        Returns indexes that could improve query performance based on historical queries.

        Args:
            limit: Maximum number of recommendations to return

        Returns:
            List of MissingIndex objects sorted by estimated improvement (descending)
        """
        pass

    @abstractmethod
    def get_slow_queries(self, top_n: int = 50, duration_ms_min: int = 100) -> List[SlowQuery]:
        """Fetch slowest queries by total/average duration.

        Returns queries that are consistently slow or causing high load.
        Filters out queries with duration < duration_ms_min to reduce noise.

        Args:
            top_n: Maximum number of slow queries to return
            duration_ms_min: Minimum average duration in milliseconds to include

        Returns:
            List of SlowQuery objects sorted by total_duration_ms (descending)
        """
        pass

    @abstractmethod
    def get_blocking_sessions(self) -> List[BlockingSession]:
        """Fetch active session blocking chains.

        Identifies lock contention and blocking relationships:
        - Session A blocked by Session B
        - Session B blocked by Session C
        - etc.

        Returns only sessions that are actively blocked or blocking others.

        Returns:
            List of BlockingSession objects in blocking chain order
        """
        pass

    @abstractmethod
    def get_wait_statistics(self, limit: int = 50) -> List[WaitStatistic]:
        """Fetch cumulative wait time statistics by wait type.

        Shows which resources are causing most waits (I/O, locks, CPU, memory, network).
        Helps identify performance bottlenecks.

        Args:
            limit: Maximum number of wait types to return

        Returns:
            List of WaitStatistic objects sorted by wait_time_ms (descending)
        """
        pass

    @abstractmethod
    def get_table_sizes(self, limit: int = 100) -> List[TableSize]:
        """Fetch table row counts and disk usage.

        Returns largest tables by row count or disk space.
        Useful for identifying tables needing partitioning or cleanup.

        Args:
            limit: Maximum number of tables to return

        Returns:
            List of TableSize objects sorted by row_count (descending)
        """
        pass

    def disconnect(self):
        """Cleanup connection if needed."""
        if self.driver:
            self.driver.disconnect()
