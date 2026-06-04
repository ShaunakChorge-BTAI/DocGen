"""
Scanner — loads SQL objects from files (folder) or a live SQL Server database.

Supports two modes controlled by Settings.source.mode:
  - "file"   : walks a directory tree looking for .sql files
  - "live_db": queries sys.sql_modules / sys.objects via pyodbc
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Re-export the shared SQLObject so callers import from one place
# ---------------------------------------------------------------------------
from .rules.base import SQLObject  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: normalise SQL Server object-type strings to canonical labels
# ---------------------------------------------------------------------------
_TYPE_MAP = {
    "P":  "Stored Procedure",
    "PC": "Stored Procedure",   # CLR stored procedure
    "V":  "View",
    "U":  "Table",
    "FN": "Function",
    "IF": "Function",
    "TF": "Function",
    "FS": "Function",
    "FT": "Function",
    "TR": "Trigger",
    "X":  "Extended Procedure",
}


def _canonical_type(raw: str) -> str:
    return _TYPE_MAP.get(raw.strip().upper(), raw.strip())


# ---------------------------------------------------------------------------
# File-based scanner
# ---------------------------------------------------------------------------

def _guess_type_from_source(source: str, filename: str) -> str:
    """Best-effort type detection from DDL source text."""
    src_up = source[:500].upper()
    if re.search(r'\bCREATE\s+(OR\s+ALTER\s+)?PROCEDURE\b', src_up):
        return "Stored Procedure"
    if re.search(r'\bCREATE\s+(OR\s+ALTER\s+)?VIEW\b', src_up):
        return "View"
    if re.search(r'\bCREATE\s+(OR\s+ALTER\s+)?TRIGGER\b', src_up):
        return "Trigger"
    if re.search(r'\bCREATE\s+(OR\s+ALTER\s+)?(FUNCTION|PROC)\b', src_up):
        return "Function"
    if re.search(r'\bCREATE\s+TABLE\b', src_up):
        return "Table"
    # Fall back to filename suffix hints
    fn = filename.lower()
    if "proc" in fn or "sp_" in fn:
        return "Stored Procedure"
    if "view" in fn or "vw_" in fn:
        return "View"
    if "func" in fn or "fn_" in fn:
        return "Function"
    if "trigger" in fn or "trg_" in fn:
        return "Trigger"
    return "Unknown"


def _extract_object_name(source: str, filename: str) -> tuple[str, str]:
    """Return (schema, name) from the first CREATE … statement."""
    m = re.search(
        r'\bCREATE\s+(?:OR\s+ALTER\s+)?'
        r'(?:PROCEDURE|PROC|VIEW|TRIGGER|FUNCTION|TABLE)\s+'
        r'(\[?(\w+)\]?\.)?\[?(\w+)\]?',
        source[:800], re.IGNORECASE)
    if m:
        schema = (m.group(2) or "dbo")
        name   = m.group(3)
        return schema, name
    # Fallback: stem of the filename
    stem = Path(filename).stem
    return "dbo", stem


def scan_files(
        root: str,
        include_schemas: Optional[List[str]] = None,
        include_types:   Optional[List[str]] = None,
        encoding: str = "utf-8-sig",
) -> Generator[SQLObject, None, None]:
    """
    Walk *root* recursively and yield one SQLObject per .sql file.

    Parameters
    ----------
    root            : root folder to scan
    include_schemas : if given, only objects in these schemas are yielded
    include_types   : if given, only objects of these types are yielded
    encoding        : file encoding (default utf-8-sig handles BOM)
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise FileNotFoundError(f"Scan root not found: {root}")

    for sql_file in sorted(root_path.rglob("*.sql")):
        try:
            source = sql_file.read_text(encoding=encoding, errors="replace")
        except Exception as exc:
            logger.warning("Cannot read %s: %s", sql_file, exc)
            continue

        schema, name = _extract_object_name(source, sql_file.name)
        obj_type     = _guess_type_from_source(source, sql_file.name)
        size_kb      = sql_file.stat().st_size / 1024

        if include_schemas and schema.lower() not in [s.lower() for s in include_schemas]:
            continue
        if include_types and obj_type not in include_types:
            continue

        yield SQLObject(
            name      = name,
            obj_type  = obj_type,
            schema    = schema,
            source    = source,
            file_path = str(sql_file),
            size_kb   = round(size_kb, 2),
        )


# ---------------------------------------------------------------------------
# Live-DB scanner
# ---------------------------------------------------------------------------

_LIVE_DB_QUERY = """
SELECT
    s.name          AS schema_name,
    o.name          AS object_name,
    o.type          AS object_type,
    m.definition    AS source_code,
    o.modify_date   AS last_modified
FROM sys.sql_modules      m
JOIN sys.objects          o ON o.object_id = m.object_id
JOIN sys.schemas          s ON s.schema_id = o.schema_id
WHERE o.is_ms_shipped = 0
  AND o.type IN ('P','V','FN','IF','TF','TR')
{schema_filter}
{type_filter}
ORDER BY s.name, o.name
"""

_TABLE_QUERY = """
SELECT
    s.name       AS schema_name,
    t.name       AS object_name,
    'U'          AS object_type,
    NULL         AS source_code,
    t.modify_date AS last_modified
FROM sys.tables  t
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.is_ms_shipped = 0
{schema_filter}
ORDER BY s.name, t.name
"""

def _scan_postgres(conn_str: str, include_schemas: list, include_types: list, include_tables: bool):
    """Fetches code objects dynamically from PostgreSQL."""
    import psycopg2
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    
    # 1. Fetch Views
    if not include_types or "View" in include_types:
        cur.execute("SELECT schemaname, viewname, definition FROM pg_views WHERE schemaname NOT IN ('pg_catalog', 'information_schema')")
        for row in cur.fetchall():
            yield SQLObject(name=row[1], obj_type="View", schema=row[0], source=row[2] or "", file_path=None)

    # 2. Fetch Functions / Procedures
    if not include_types or "Function" in include_types or "Stored Procedure" in include_types:
        cur.execute("""
            SELECT n.nspname, p.proname, p.prosrc
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
        """)
        for row in cur.fetchall():
            yield SQLObject(name=row[1], obj_type="Function", schema=row[0], source=row[2] or "", file_path=None)

    # 3. Fetch Tables
    if include_tables and (not include_types or "Table" in include_types):
        cur.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema')")
        for row in cur.fetchall():
            yield SQLObject(name=row[1], obj_type="Table", schema=row[0], source="", file_path=None)
            
    conn.close()


def scan_live_db(
        connection_string: str,
        include_schemas:   Optional[List[str]] = None,
        include_types:     Optional[List[str]] = None,
        include_tables:    bool = True,
) -> Generator[SQLObject, None, None]:
    """
    Connect to SQL Server and yield one SQLObject per database object.

    Parameters
    ----------
    connection_string : pyodbc connection string
    include_schemas   : filter by schema (None = all)
    include_types     : canonical type strings to include
    include_tables    : also scan sys.tables (which have no sql_modules entry)
    """

    if connection_string.startswith("postgresql://"):
        yield from _scan_postgres(connection_string, include_schemas, include_types, include_tables)
        return  # Exit function so it doesn't run the MSSQL code below

    if "DRIVER=" not in connection_string.upper():
        logger.warning("Skipping deep T-SQL code scan: Connection string does not use ODBC DRIVER (likely PostGreQL/MyQL). It's recommended to use a DSN or include DRIVER={ODBC Driver 17 for SQL Server} for better reliability.")

    try:
        import pyodbc  # type: ignore
    except ImportError:
        raise RuntimeError("pyodbc is required for live-DB scanning. Install it first.")

    logger.debug("scan_live_db called")
    logger.debug("connection_string starts with: %s", connection_string[:80])

    schema_filter = ""
    type_filter   = ""
    if include_schemas:
        quoted = ", ".join(f"'{s}'" for s in include_schemas)
        schema_filter = f"  AND s.name IN ({quoted})"
    if include_types:
        # Convert canonical → SQL Server type codes
        rev_map = {v: k for k, v in _TYPE_MAP.items()}
        codes = list({rev_map[t] for t in include_types if t in rev_map})
        if codes:
            quoted = ", ".join(f"'{c}'" for c in codes)
            type_filter = f"  AND o.type IN ({quoted})"

    query = _LIVE_DB_QUERY.format(
        schema_filter=schema_filter,
        type_filter=type_filter,
    )

    try:
        # Debug: log the connection string (mask password)
        if "PWD=" in connection_string:
            idx = connection_string.find("PWD=") + 4
            end_idx = connection_string.find(";", idx)
            if end_idx == -1:
                end_idx = len(connection_string)
            debug_str = connection_string[:idx] + "***" + connection_string[end_idx:]
        else:
            debug_str = connection_string
        logger.info("[scanner.scan_live_db] Attempting pyodbc connection: %s", debug_str)
        conn = pyodbc.connect(connection_string, timeout=30)
    except pyodbc.Error as exc:
        logger.error("[scanner] Connection failed with: %s", debug_str)
        raise ConnectionError(f"Cannot connect to SQL Server: {exc}") from exc

    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        logger.info("Live-DB scan: retrieved %d objects from sys.sql_modules", len(rows))

        for row in rows:
            schema_name, obj_name, obj_type_code, source, _ = row
            canonical = _canonical_type(obj_type_code)
            if include_types and canonical not in include_types:
                continue
            yield SQLObject(
                name      = obj_name,
                obj_type  = canonical,
                schema    = schema_name,
                source    = source or "",
                file_path = None,
            )

        if include_tables and (not include_types or "Table" in include_types):
            tbl_query = _TABLE_QUERY.format(schema_filter=schema_filter)
            cursor.execute(tbl_query)
            for row in cursor.fetchall():
                schema_name, obj_name, _, _, _ = row
                yield SQLObject(
                    name     = obj_name,
                    obj_type = "Table",
                    schema   = schema_name,
                    source   = "",
                    file_path= None,
                )

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Unified entry point used by the analyser
# ---------------------------------------------------------------------------

def load_objects(cfg) -> Generator[SQLObject, None, None]:
    """
    Dispatch to the right scanner based on cfg.source.mode.

    cfg is a dbanalyser.config.Settings instance.
    """
    mode = cfg.source.mode.lower()

    if mode == "file":
        logger.info("Scanning files in: %s", cfg.source.file_path)
        yield from scan_files(
            root            = cfg.source.file_path,
            include_schemas = cfg.scope.schemas or None,
            include_types   = cfg.scope.object_types or None,
        )

    elif mode == "live_db":
        logger.info("Scanning live SQL Server database")
        yield from scan_live_db(
            connection_string = cfg.source.connection_string,
            include_schemas   = cfg.scope.schemas or None,
            include_types     = cfg.scope.object_types or None,
        )

    else:
        raise ValueError(f"Unknown source.mode '{mode}'. Use 'file' or 'live_db'.")
