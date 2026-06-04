"""
DMV (Dynamic Management View) analysis — live SQL Server only.

Functions
---------
analyse_index_usage     — unused / hot indexes from sys.dm_db_index_usage_stats
analyse_missing_indexes — missing index hints from sys.dm_db_missing_index_details
analyse_slow_queries    — top CPU/elapsed from sys.dm_exec_query_stats
analyse_wait_stats      — waits from sys.dm_os_wait_stats
analyse_blocking_chains — active blocks from sys.dm_exec_requests
analyse_table_sizes     — row / size data from sys.allocation_units

All functions return a pandas DataFrame.  Connection string is pyodbc-compatible.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _query(conn_str: str, sql: str, params=None) -> pd.DataFrame:
    """Run *sql* and return a DataFrame.  Raises on connection errors."""
    try:
        import pyodbc  # type: ignore
    except ImportError:
        raise RuntimeError("pyodbc is required for DMV analysis. pip install pyodbc")

    try:
        conn = pyodbc.connect(conn_str, timeout=30)
        df = pd.read_sql(sql, conn, params=params)
        conn.close()
        return df
    except Exception as exc:
        logger.error("DMV query failed: %s", exc)
        raise


# ---------------------------------------------------------------------------
# 1. Index usage
# ---------------------------------------------------------------------------

_INDEX_USAGE_SQL = """
SELECT
    OBJECT_SCHEMA_NAME(i.object_id)          AS schema_name,
    OBJECT_NAME(i.object_id)                 AS table_name,
    i.name                                   AS index_name,
    i.type_desc                              AS index_type,
    ISNULL(us.user_seeks,  0)                AS user_seeks,
    ISNULL(us.user_scans,  0)                AS user_scans,
    ISNULL(us.user_lookups,0)                AS user_lookups,
    ISNULL(us.user_updates,0)                AS user_updates,
    ISNULL(us.last_user_seek, NULL)          AS last_user_seek,
    ISNULL(us.last_user_scan, NULL)          AS last_user_scan,
    i.fill_factor,
    p.rows                                   AS row_count
FROM sys.indexes i
JOIN sys.objects o ON o.object_id = i.object_id
LEFT JOIN sys.dm_db_index_usage_stats us
       ON us.object_id  = i.object_id
      AND us.index_id   = i.index_id
      AND us.database_id= DB_ID()
LEFT JOIN sys.partitions p
       ON p.object_id = i.object_id
      AND p.index_id  = i.index_id
WHERE o.is_ms_shipped = 0
  AND i.type > 0            -- exclude heaps
ORDER BY user_seeks + user_scans + user_lookups ASC,
         user_updates DESC
"""


def analyse_index_usage(conn_str: str) -> pd.DataFrame:
    """Return index usage statistics from the current SQL Server database."""
    logger.info("Analysing index usage ...")
    df = _query(conn_str, _INDEX_USAGE_SQL)
    df["total_reads"]  = df["user_seeks"] + df["user_scans"] + df["user_lookups"]
    df["read_to_write"] = df.apply(
        lambda r: round(r.total_reads / r.user_updates, 2) if r.user_updates else None,
        axis=1,
    )
    df["flag"] = df.apply(
        lambda r: "UNUSED"         if r.total_reads == 0 and r.user_updates > 0
        else "WRITE_HEAVY"         if r.user_updates > 0 and r.total_reads < r.user_updates * 0.1
        else "HOT"                 if r.total_reads > 10000
        else "",
        axis=1,
    )
    return df


# ---------------------------------------------------------------------------
# 2. Missing indexes
# ---------------------------------------------------------------------------

_MISSING_INDEX_SQL = """
SELECT TOP 50
    mid.database_id,
    OBJECT_SCHEMA_NAME(mid.object_id, mid.database_id)  AS schema_name,
    OBJECT_NAME(mid.object_id, mid.database_id)         AS table_name,
    mid.equality_columns,
    mid.inequality_columns,
    mid.included_columns,
    migs.unique_compiles,
    migs.user_seeks,
    migs.user_scans,
    ROUND(migs.avg_total_user_cost * migs.avg_user_impact
          * (migs.user_seeks + migs.user_scans), 2)     AS improvement_measure,
    migs.avg_user_impact                                AS avg_impact_pct
FROM sys.dm_db_missing_index_details   mid
JOIN sys.dm_db_missing_index_group_stats migs
  ON migs.group_handle IN (
       SELECT group_handle
       FROM sys.dm_db_missing_index_groups
       WHERE index_handle = mid.index_handle
     )
WHERE mid.database_id = DB_ID()
ORDER BY improvement_measure DESC
"""


def analyse_missing_indexes(conn_str: str) -> pd.DataFrame:
    logger.info("Analysing missing indexes ...")
    df = _query(conn_str, _MISSING_INDEX_SQL)
    # Build a CREATE INDEX suggestion column
    def _create_suggestion(row) -> str:
        eq  = row.equality_columns   or ""
        iq  = row.inequality_columns or ""
        inc = row.included_columns   or ""
        key_cols = ", ".join(filter(None, [eq, iq]))
        inc_part = f" INCLUDE ({inc})" if inc else ""
        return (
            f"CREATE NONCLUSTERED INDEX [IX_{row.table_name}_suggestion] "
            f"ON [{row.schema_name}].[{row.table_name}] ({key_cols}){inc_part};"
        )
    if not df.empty:
        df["create_statement"] = df.apply(_create_suggestion, axis=1)
    return df


# ---------------------------------------------------------------------------
# 3. Slow queries
# ---------------------------------------------------------------------------

_SLOW_QUERY_SQL = """
SELECT TOP 50
    qs.total_elapsed_time / qs.execution_count / 1000   AS avg_elapsed_ms,
    qs.total_cpu_time     / qs.execution_count / 1000   AS avg_cpu_ms,
    qs.total_logical_reads/ qs.execution_count          AS avg_logical_reads,
    qs.execution_count,
    qs.total_elapsed_time / 1000                        AS total_elapsed_ms,
    qs.total_cpu_time     / 1000                        AS total_cpu_ms,
    qs.creation_time                                    AS plan_creation_time,
    SUBSTRING(qt.text, (qs.statement_start_offset/2)+1,
              (CASE qs.statement_end_offset
                 WHEN -1 THEN DATALENGTH(qt.text)
                 ELSE qs.statement_end_offset
               END - qs.statement_start_offset)/2 + 1) AS query_text,
    DB_NAME(qt.dbid)                                    AS database_name,
    OBJECT_NAME(qt.objectid, qt.dbid)                   AS object_name,
    qp.query_plan
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle)   qt
CROSS APPLY sys.dm_exec_query_plan(qs.plan_handle) qp
WHERE qs.execution_count > 1
ORDER BY avg_elapsed_ms DESC
"""


def analyse_slow_queries(conn_str: str) -> pd.DataFrame:
    logger.info("Analysing slow queries ...")
    df = _query(conn_str, _SLOW_QUERY_SQL)
    # Drop the raw XML plan to keep the DataFrame lightweight
    if "query_plan" in df.columns:
        df = df.drop(columns=["query_plan"])
    return df


# ---------------------------------------------------------------------------
# 4. Wait statistics
# ---------------------------------------------------------------------------

_WAIT_STATS_SQL = """
SELECT TOP 30
    wait_type,
    waiting_tasks_count,
    wait_time_ms,
    max_wait_time_ms,
    signal_wait_time_ms,
    ROUND(100.0 * wait_time_ms / NULLIF(SUM(wait_time_ms) OVER (), 0), 2) AS pct_of_total,
    CASE
        WHEN wait_type LIKE 'LCK%'           THEN 'Locking'
        WHEN wait_type LIKE 'PAGEIOLATCH%'   THEN 'I/O'
        WHEN wait_type LIKE 'SOS_SCHEDULER%' THEN 'CPU pressure'
        WHEN wait_type LIKE 'CXPACKET%'      THEN 'Parallelism'
        WHEN wait_type LIKE 'ASYNC_NETWORK%' THEN 'Network'
        ELSE 'Other'
    END AS wait_category
FROM sys.dm_os_wait_stats
WHERE wait_type NOT IN (
    'SLEEP_TASK','SQLTRACE_BUFFER_FLUSH','WAITFOR','LAZYWRITER_SLEEP',
    'SLEEP_DBSTARTUP','SLEEP_DBTASK','SLEEP_TEMPDBSTARTUP','SNI_HTTP_ACCEPT',
    'DISPATCHER_QUEUE_SEMAPHORE','XE_DISPATCHER_WAIT','REQUEST_FOR_DEADLOCK_SEARCH',
    'RESOURCE_QUEUE','SERVER_IDLE_CHECK','SLEEP_SYSTEMTASK','SLEEP_TEMPDBSTARTUP',
    'CLR_AUTO_EVENT','HADR_WORK_QUEUE','BROKER_TO_FLUSH','CHECKPOINT_QUEUE',
    'DBMIRROR_EVENTS_QUEUE','SQLTRACE_INCREMENTAL_FLUSH_SLEEP',
    'WAIT_XTP_OFFLINE_CKPT_NEW_LOG'
)
  AND waiting_tasks_count > 0
ORDER BY wait_time_ms DESC
"""


def analyse_wait_stats(conn_str: str) -> pd.DataFrame:
    logger.info("Analysing wait statistics ...")
    return _query(conn_str, _WAIT_STATS_SQL)


# ---------------------------------------------------------------------------
# 5. Blocking chains
# ---------------------------------------------------------------------------

_BLOCKING_SQL = """
SELECT
    r.session_id,
    r.blocking_session_id,
    r.wait_type,
    r.wait_time / 1000                          AS wait_time_sec,
    r.status,
    r.command,
    DB_NAME(r.database_id)                      AS database_name,
    SUBSTRING(qt.text, (r.statement_start_offset/2)+1,
              (CASE r.statement_end_offset
                 WHEN -1 THEN DATALENGTH(qt.text)
                 ELSE r.statement_end_offset
               END - r.statement_start_offset)/2 + 1) AS current_statement,
    r.cpu_time / 1000                           AS cpu_time_sec,
    r.total_elapsed_time / 1000                 AS elapsed_sec,
    r.reads,
    r.writes,
    s.login_name,
    s.host_name,
    s.program_name
FROM sys.dm_exec_requests r
JOIN sys.dm_exec_sessions  s ON s.session_id = r.session_id
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) qt
WHERE r.session_id <> @@SPID
  AND r.session_id > 50   -- exclude system sessions
ORDER BY r.blocking_session_id DESC, r.wait_time DESC
"""


def analyse_blocking_chains(conn_str: str) -> pd.DataFrame:
    logger.info("Analysing blocking chains ...")
    return _query(conn_str, _BLOCKING_SQL)


# ---------------------------------------------------------------------------
# 6. Table sizes
# ---------------------------------------------------------------------------

_TABLE_SIZE_SQL = """
SELECT
    s.name                              AS schema_name,
    t.name                              AS table_name,
    SUM(p.rows)                         AS row_count,
    CAST(SUM(a.total_pages) * 8.0 / 1024  AS DECIMAL(10,2)) AS total_size_mb,
    CAST(SUM(a.used_pages)  * 8.0 / 1024  AS DECIMAL(10,2)) AS used_size_mb,
    CAST(SUM(a.data_pages)  * 8.0 / 1024  AS DECIMAL(10,2)) AS data_size_mb,
    COUNT(DISTINCT i.index_id) - 1      AS index_count
FROM sys.tables         t
JOIN sys.schemas        s  ON s.schema_id  = t.schema_id
JOIN sys.indexes        i  ON i.object_id  = t.object_id
JOIN sys.partitions     p  ON p.object_id  = i.object_id
                          AND p.index_id   = i.index_id
JOIN sys.allocation_units a ON a.container_id = p.partition_id
WHERE t.is_ms_shipped = 0
GROUP BY s.name, t.name
ORDER BY total_size_mb DESC
"""


def analyse_table_sizes(conn_str: str) -> pd.DataFrame:
    logger.info("Analysing table sizes ...")
    return _query(conn_str, _TABLE_SIZE_SQL)


# ---------------------------------------------------------------------------
# Convenience: run all DMV checks and return a dict
# ---------------------------------------------------------------------------

def run_all_dmv_checks(conn_str: str) -> dict[str, pd.DataFrame]:
    """
    Run all 6 DMV analyses and return results as a dictionary.
    Keys match the CSV filenames used by the legacy notebook.
    """
    results: dict[str, pd.DataFrame] = {}
    checks = {
        "dmv_index_usage":    analyse_index_usage,
        "dmv_missing_indexes":analyse_missing_indexes,
        "dmv_slow_queries":   analyse_slow_queries,
        "dmv_wait_stats":     analyse_wait_stats,
        "dmv_blocking_chains":analyse_blocking_chains,
        "dmv_table_sizes":    analyse_table_sizes,
    }
    for key, fn in checks.items():
        try:
            results[key] = fn(conn_str)
            logger.info("%s: %d rows", key, len(results[key]))
        except Exception as exc:
            logger.warning("Skipping %s — %s", key, exc)
            results[key] = pd.DataFrame()
    return results
