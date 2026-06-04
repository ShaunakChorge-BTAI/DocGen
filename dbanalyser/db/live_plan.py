"""
Live Execution Plan Fetcher
============================
Connects to a SQL Server database via pyodbc and retrieves the estimated
XML execution plan using SET SHOWPLAN_XML ON.

SAFE: SHOWPLAN_XML mode does NOT execute DML — it only plans the statement.
This lets us capture real optimizer plans for stored procedures and queries
without modifying any data.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)


def fetch_estimated_plan(
    connection_string: str,
    object_name: str,
    params_sql: str = "",
    timeout_sec: int = 30,
) -> tuple[str, str]:
    """
    Fetch an estimated XML execution plan for a stored procedure or ad-hoc query.

    Uses SET SHOWPLAN_XML ON — does NOT execute the procedure body, so it is
    safe to call on any object including INSERT/UPDATE/DELETE procedures.

    Args:
        connection_string : pyodbc DSN / connection string
        object_name       : schema.proc_name  *or*  raw T-SQL query text
        params_sql        : optional EXEC parameters, e.g. "@Id=0, @Date='2020-01-01'"
        timeout_sec       : connection timeout in seconds

    Returns:
        (xml_plan: str, error: str)  — one will always be empty string.
    """
    try:
        import pyodbc  # type: ignore
    except ImportError:
        return "", "pyodbc not installed. Run: pip install pyodbc"

    # Determine if object_name is a procedure name or raw SQL
    _name = object_name.strip()
    is_proc = bool(re.match(
        r'^[\w\[\]]+\.[\w\[\]]+$|^[\w\[\]]+$',
        re.sub(r'\s+', ' ', _name)
    )) and not _name.upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE", "WITH"))

    if is_proc:
        exec_stmt = f"EXEC {_name}" + (f" {params_sql}" if params_sql.strip() else "")
    else:
        exec_stmt = _name  # treat as raw SQL

    try:
        conn = pyodbc.connect(connection_string, timeout=timeout_sec)
        conn.autocommit = True
        cur = conn.cursor()
        plan_xml = ""
        try:
            cur.execute("SET SHOWPLAN_XML ON")
            cur.execute(exec_stmt)
            row = cur.fetchone()
            plan_xml = str(row[0]) if row and row[0] else ""
        finally:
            try:
                cur.execute("SET SHOWPLAN_XML OFF")
            except Exception:
                pass
            conn.close()
        return plan_xml, ""
    except Exception as exc:
        log.warning("fetch_estimated_plan failed for '%s': %s", object_name, exc)
        return "", str(exc)


def fetch_actual_plan_stats(
    connection_string: str,
    object_name: str,
    params_sql: str = "",
    timeout_sec: int = 30,
) -> tuple[str, str]:
    """
    Capture STATISTICS XML (actual plan + row counts) for a stored procedure.

    WARNING: This EXECUTES the procedure — use only on read-only procedures
    or when the caller knows execution is safe.

    Returns (xml_plan, error).
    """
    try:
        import pyodbc  # type: ignore
    except ImportError:
        return "", "pyodbc not installed."

    _name = object_name.strip()
    exec_stmt = f"EXEC {_name}" + (f" {params_sql}" if params_sql.strip() else "")

    try:
        conn = pyodbc.connect(connection_string, timeout=timeout_sec)
        conn.autocommit = False
        cur = conn.cursor()
        plan_parts: list[str] = []
        try:
            cur.execute("SET STATISTICS XML ON")
            cur.execute(exec_stmt)
            # Drain all result sets and collect XML plan rows
            while True:
                rows = cur.fetchall()
                for row in rows:
                    for col in row:
                        s = str(col) if col else ""
                        if s.startswith("<ShowPlanXML") or s.startswith("<?xml"):
                            plan_parts.append(s)
                if not cur.nextset():
                    break
        finally:
            try:
                cur.execute("SET STATISTICS XML OFF")
                conn.rollback()  # always rollback — don't persist any side-effects
            except Exception:
                pass
            conn.close()
        return "\n".join(plan_parts), ""
    except Exception as exc:
        log.warning("fetch_actual_plan_stats failed for '%s': %s", object_name, exc)
        return "", str(exc)


def resolve_connection_string(db_registry_id: int) -> str:
    """
    Look up the connection string for a registered database by id.
    Returns empty string if not found or DB is file-mode.
    """
    try:
        from dbanalyser.db.repository import get_db_registry_by_id
        row = get_db_registry_by_id(db_registry_id)
        if not row:
            return ""
        # Explicit connection string takes priority
        if row.get("connection_string"):
            return row["connection_string"]
        # Build from parts
        host    = row.get("host", "localhost")
        port    = row.get("port", 1433)
        db_name = row.get("database_name", "")
        if row.get("use_windows_auth", True):
            return (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={host},{port};DATABASE={db_name};Trusted_Connection=yes;"
            )
        user = row.get("username", "")
        return (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={host},{port};DATABASE={db_name};"
            f"UID={user};PWD=;"
        )
    except Exception as exc:
        log.warning("resolve_connection_string failed: %s", exc)
        return ""
