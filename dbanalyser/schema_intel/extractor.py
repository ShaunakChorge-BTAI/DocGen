"""
Schema Extractor
=================
Pulls database schema from two sources:

1. Live SQL Server (via pyodbc) — tables, columns, indexes, procedures
2. SQLObject list (from file-based scanner) — tables and procedures from SQL source

Returns plain dicts suitable for upsert_schema_object().
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class SchemaObject:
    object_type:   str                # table | column | procedure | view | index
    schema_name:   str = "dbo"
    object_name:   str = ""
    parent_name:   str = ""           # for columns/indexes: parent table name
    data_type:     Optional[str] = None
    is_nullable:   bool = True
    is_primary_key:bool = False
    is_foreign_key:bool = False
    definition:    str = ""
    extra:         Dict[str, Any] = field(default_factory=dict)


# ── Live SQL Server extraction ────────────────────────────────────────────────

_SQL_TABLES = """
SELECT
    s.name            AS schema_name,
    t.name            AS table_name,
    ep.value          AS description
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id = t.schema_id
LEFT JOIN sys.extended_properties ep
    ON ep.major_id   = t.object_id
    AND ep.minor_id  = 0
    AND ep.name      = 'MS_Description'
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name
"""

_SQL_COLUMNS = """
SELECT
    s.name            AS schema_name,
    t.name            AS table_name,
    c.name            AS column_name,
    tp.name           AS data_type,
    c.max_length,
    c.is_nullable,
    c.column_id,
    ISNULL(pk.is_pk, 0)  AS is_primary_key,
    ISNULL(fk.is_fk, 0)  AS is_foreign_key,
    ep.value          AS description
FROM sys.columns c
JOIN sys.tables  t  ON t.object_id = c.object_id
JOIN sys.schemas s  ON s.schema_id = t.schema_id
JOIN sys.types   tp ON tp.user_type_id = c.user_type_id
LEFT JOIN (
    SELECT ic.object_id, ic.column_id, 1 AS is_pk
    FROM sys.index_columns ic
    JOIN sys.indexes ix ON ix.object_id = ic.object_id AND ix.index_id = ic.index_id
    WHERE ix.is_primary_key = 1
) pk ON pk.object_id = c.object_id AND pk.column_id = c.column_id
LEFT JOIN (
    SELECT fkc.parent_object_id AS object_id, fkc.parent_column_id AS column_id, 1 AS is_fk
    FROM sys.foreign_key_columns fkc
) fk ON fk.object_id = c.object_id AND fk.column_id = c.column_id
LEFT JOIN sys.extended_properties ep
    ON ep.major_id   = c.object_id
    AND ep.minor_id  = c.column_id
    AND ep.name      = 'MS_Description'
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name, c.column_id
"""

_SQL_PROCEDURES = """
SELECT
    s.name   AS schema_name,
    p.name   AS proc_name,
    m.definition
FROM sys.procedures p
JOIN sys.schemas    s ON s.schema_id   = p.schema_id
JOIN sys.sql_modules m ON m.object_id  = p.object_id
WHERE p.is_ms_shipped = 0
ORDER BY s.name, p.name
"""

_SQL_VIEWS = """
SELECT
    s.name   AS schema_name,
    v.name   AS view_name,
    m.definition
FROM sys.views   v
JOIN sys.schemas s ON s.schema_id  = v.schema_id
JOIN sys.sql_modules m ON m.object_id = v.object_id
WHERE v.is_ms_shipped = 0
ORDER BY s.name, v.name
"""

_SQL_INDEXES = """
SELECT
    s.name   AS schema_name,
    t.name   AS table_name,
    i.name   AS index_name,
    i.type_desc,
    i.is_unique,
    i.is_primary_key,
    STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS key_columns
FROM sys.indexes       i
JOIN sys.tables        t  ON t.object_id  = i.object_id
JOIN sys.schemas       s  ON s.schema_id  = t.schema_id
JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns       c  ON c.object_id  = ic.object_id AND c.column_id = ic.column_id
WHERE t.is_ms_shipped = 0 AND i.type > 0
GROUP BY s.name, t.name, i.name, i.type_desc, i.is_unique, i.is_primary_key
ORDER BY s.name, t.name, i.name
"""


def extract_schema_from_live_db(connection_string: str) -> List[SchemaObject]:
    """
    Extract complete schema from a live SQL Server database.

    Returns a flat list of SchemaObject instances (tables, columns, procedures,
    views, indexes).
    """
    try:
        import pyodbc  # type: ignore
    except ImportError:
        log.error("pyodbc not installed — cannot connect to SQL Server")
        return []

    objects: List[SchemaObject] = []
    try:
        conn = pyodbc.connect(connection_string, timeout=30)
        cur  = conn.cursor()

        # Tables
        for row in cur.execute(_SQL_TABLES).fetchall():
            objects.append(SchemaObject(
                object_type="table",
                schema_name=row[0],
                object_name=row[1],
                definition=str(row[2] or ""),
            ))

        # Columns
        for row in cur.execute(_SQL_COLUMNS).fetchall():
            objects.append(SchemaObject(
                object_type="column",
                schema_name=row[0],
                parent_name=row[1],
                object_name=row[2],
                data_type=row[3],
                is_nullable=bool(row[5]),
                is_primary_key=bool(row[7]),
                is_foreign_key=bool(row[8]),
                definition=str(row[9] or ""),
                extra={"max_length": row[4]},
            ))

        # Procedures
        for row in cur.execute(_SQL_PROCEDURES).fetchall():
            objects.append(SchemaObject(
                object_type="procedure",
                schema_name=row[0],
                object_name=row[1],
                definition=(row[2] or "")[:2000],   # cap at 2 KB for embedding
            ))

        # Views
        for row in cur.execute(_SQL_VIEWS).fetchall():
            objects.append(SchemaObject(
                object_type="view",
                schema_name=row[0],
                object_name=row[1],
                definition=(row[2] or "")[:2000],
            ))

        # Indexes (STRING_AGG may not be available on SQL Server < 2017 — catch gracefully)
        try:
            for row in cur.execute(_SQL_INDEXES).fetchall():
                objects.append(SchemaObject(
                    object_type="index",
                    schema_name=row[0],
                    parent_name=row[1],
                    object_name=row[2],
                    is_primary_key=bool(row[5]),
                    definition=f"{row[3]} on ({row[6]})",
                    extra={"is_unique": bool(row[4])},
                ))
        except Exception as exc:
            log.warning("Index extraction skipped (may require SQL Server 2017+): %s", exc)

        conn.close()
        log.info("Extracted %d schema objects from live DB", len(objects))

    except Exception as exc:
        log.error("Schema extraction failed: %s", exc)

    return objects


# ── File-based (SQLObject) extraction ────────────────────────────────────────

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:\[?(\w+)\]?\.)?\[?(\w+)\]?", re.IGNORECASE
)
_COLUMN_RE = re.compile(
    r"^\s+\[?(\w+)\]?\s+(n?varchar|n?char|int|bigint|smallint|tinyint|bit|"
    r"decimal|numeric|float|real|money|smallmoney|date(?:time2?)?|"
    r"uniqueidentifier|varbinary|image|text|ntext|xml|geography|geometry)"
    r"(?:\s*\([^)]+\))?",
    re.IGNORECASE | re.MULTILINE,
)
_CREATE_PROC_RE = re.compile(
    r"CREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+(?:\[?(\w+)\]?\.)?\[?(\w+)\]?",
    re.IGNORECASE,
)
_CREATE_VIEW_RE = re.compile(
    r"CREATE\s+(?:OR\s+ALTER\s+)?VIEW\s+(?:\[?(\w+)\]?\.)?\[?(\w+)\]?",
    re.IGNORECASE,
)


def extract_schema_from_objects(sql_objects: list) -> List[SchemaObject]:
    """
    Extract schema from a list of SQLObject instances (file-based scanner output).

    Args:
        sql_objects: list of dbanalyser.engine.rules.base.SQLObject

    Returns:
        List of SchemaObject.
    """
    results: List[SchemaObject] = []
    for obj in sql_objects:
        src  = obj.source
        name = obj.name
        sch  = obj.schema or "dbo"
        ot   = (obj.obj_type or "").lower()

        if ot in ("table",):
            results.append(SchemaObject(
                object_type="table", schema_name=sch, object_name=name,
                definition=src[:1000],
            ))
            # Extract column names from CREATE TABLE body
            for m in _COLUMN_RE.finditer(src):
                results.append(SchemaObject(
                    object_type="column", schema_name=sch,
                    parent_name=name, object_name=m.group(1),
                    data_type=m.group(2), definition="",
                ))

        elif ot in ("stored procedure",):
            results.append(SchemaObject(
                object_type="procedure", schema_name=sch, object_name=name,
                definition=src[:2000],
            ))

        elif ot in ("view",):
            results.append(SchemaObject(
                object_type="view", schema_name=sch, object_name=name,
                definition=src[:2000],
            ))

        elif ot in ("function",):
            results.append(SchemaObject(
                object_type="function", schema_name=sch, object_name=name,
                definition=src[:2000],
            ))

    log.info("Extracted %d schema objects from %d SQL files", len(results), len(sql_objects))
    return results
