"""
Object Dependency Analyzer
===========================
Queries SQL Server system views (live) or the schema_objects store (offline)
to produce inbound + outbound dependency graphs for any database object.

Live mode  : uses sys.dm_sql_referenced_entities + sys.sql_expression_dependencies
Offline mode: parses source text in the schema_objects vector store
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ── List all objects from live database ─────────────────────────────────────

def list_objects_live(
    connection_string: str,
    object_type: str = 'table',
    limit: int = 500,
) -> Dict[str, Any]:
    """
    Query SQL Server to list all objects of a specific type.

    Args:
        connection_string: SQL Server connection string (format: "Server=host;Database=db;User=user;Password=pass;" or ODBC)
        object_type: 'table', 'view', 'stored procedure', 'function', 'trigger'
        limit: max number of objects to return

    Returns:
        {
          "objects": [...],  # list of objects
          "error": ""
        }

    Each object is a dict with:
        schema_name, object_name, object_type
    """
    result: Dict[str, Any] = {"objects": [], "error": ""}

    # Map friendly names to SQL Server type codes
    type_map = {
        'table': ['U'],  # User table
        'view': ['V'],  # View
        'stored procedure': ['P', 'RF'],  # Stored proc or replication filter proc
        'function': ['FN', 'IF', 'TF', 'FS', 'FT'],  # All function types
        'trigger': ['TR'],  # Trigger
    }

    type_codes = type_map.get(object_type.lower(), ['U'])
    type_codes_str = ','.join([f"'{code}'" for code in type_codes])

    sql = f"""
    SELECT TOP {limit}
        SCHEMA_NAME(o.schema_id) AS schema_name,
        o.name AS object_name,
        o.type_desc AS object_type
    FROM sys.objects o
    WHERE o.type IN ({type_codes_str})
    AND o.is_ms_shipped = 0
    ORDER BY SCHEMA_NAME(o.schema_id), o.name
    """

    # Try pymssql first (no ODBC required)
    try:
        import pymssql  # type: ignore

        # Parse connection string to extract host, port, database, user, password
        conn_params = _parse_connection_string(connection_string)
        conn = pymssql.connect(
            server=conn_params.get('server', 'localhost'),
            port=int(conn_params.get('port', 1433)),
            database=conn_params.get('database', ''),
            user=conn_params.get('user', ''),
            password=conn_params.get('password', ''),
            timeout=30
        )
        cur = conn.cursor()
        cur.execute(sql)

        result["objects"] = [
            {
                "schema_name": r[0] or "dbo",
                "object_name": r[1] or "",
                "object_type": r[2] or object_type,
            }
            for r in cur.fetchall()
        ]
        conn.close()
        return result
    except ImportError:
        pass  # Fall back to pyodbc
    except Exception as exc:
        log.debug(f"pymssql failed, trying pyodbc: {exc}")
        pass  # Fall back to pyodbc

    # Fall back to pyodbc
    try:
        import pyodbc  # type: ignore
        conn = pyodbc.connect(connection_string, timeout=30)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, type_codes)

        result["objects"] = [
            {
                "schema_name": r[0] or "dbo",
                "object_name": r[1] or "",
                "object_type": r[2] or object_type,
            }
            for r in cur.fetchall()
        ]
        conn.close()
    except Exception as exc:
        result["error"] = str(exc)

    return result


def _parse_connection_string(conn_str: str) -> Dict[str, str]:
    """Parse a connection string (ODBC or standard format) into components."""
    params = {}

    # Handle ODBC format: DRIVER={...};SERVER=...;DATABASE=...;...
    if 'DRIVER=' in conn_str:
        parts = conn_str.split(';')
        for part in parts:
            if '=' in part:
                key, val = part.split('=', 1)
                key = key.strip().lower()
                val = val.strip().rstrip('}').lstrip('{')

                if key == 'server':
                    # Handle "host,port" format
                    if ',' in val:
                        host, port = val.split(',')
                        params['server'] = host
                        params['port'] = port
                    else:
                        params['server'] = val
                elif key == 'database':
                    params['database'] = val
                elif key == 'uid':
                    params['user'] = val
                elif key == 'pwd':
                    params['password'] = val
                elif key == 'trusted_connection' and val.lower() == 'yes':
                    # Windows auth - no user/pass needed
                    params['user'] = ''
                    params['password'] = ''
    else:
        # Handle standard format: Server=host;Database=db;User=user;Password=pass;
        parts = conn_str.split(';')
        for part in parts:
            if '=' in part:
                key, val = part.split('=', 1)
                key = key.strip().lower()
                val = val.strip()
                if key == 'server':
                    if ',' in val:
                        host, port = val.split(',')
                        params['server'] = host
                        params['port'] = port
                    else:
                        params['server'] = val
                elif key == 'database':
                    params['database'] = val
                elif key in ('user', 'uid'):
                    params['user'] = val
                elif key in ('password', 'pwd'):
                    params['password'] = val

    return params


# ── Live database dependency query ───────────────────────────────────────────

def get_dependencies_live(
    connection_string: str,
    schema_name: str,
    object_name: str,
    timeout_sec: int = 30,
) -> Dict[str, Any]:
    """
    Query SQL Server for object dependencies via system DMVs.

    Returns::

        {
          "references":    [...],   # objects THIS object depends on
          "referenced_by": [...],   # objects that depend on THIS object
          "error": ""
        }

    Each item in the lists is a dict with:
        schema_name, object_name, object_type, column_name (if column ref)
    """
    result: Dict[str, Any] = {"references": [], "referenced_by": [], "error": ""}
    try:
        import pyodbc  # type: ignore
    except ImportError:
        result["error"] = "pyodbc not installed. Run: pip install pyodbc"
        return result

    full_name = f"{schema_name}.{object_name}" if schema_name else object_name

    _SQL_REFS = """
        SELECT
            COALESCE(referenced_schema_name, 'dbo') AS schema_name,
            referenced_entity_name                   AS object_name,
            referenced_class_desc                    AS object_type,
            COALESCE(referenced_minor_name, '')      AS column_name
        FROM sys.dm_sql_referenced_entities(?, 'OBJECT')
        WHERE referenced_entity_name IS NOT NULL
        ORDER BY referenced_class_desc, referenced_entity_name
    """

    _SQL_REFBY = """
        SELECT
            SCHEMA_NAME(o.schema_id) AS schema_name,
            o.name                   AS object_name,
            o.type_desc              AS object_type,
            o.type                   AS type_code
        FROM sys.sql_expression_dependencies d
        JOIN sys.objects o ON o.object_id = d.referencing_id
        WHERE d.referenced_id = OBJECT_ID(?)
        ORDER BY o.type_desc, o.name
    """

    try:
        conn = pyodbc.connect(connection_string, timeout=timeout_sec)
        conn.autocommit = True
        cur = conn.cursor()

        # Outbound — what this object references
        try:
            cur.execute(_SQL_REFS, (full_name,))
            result["references"] = [
                {
                    "schema_name": r[0] or "dbo",
                    "object_name": r[1] or "",
                    "object_type": _normalise_type(r[2] or ""),
                    "column_name": r[3] or "",
                }
                for r in cur.fetchall()
            ]
        except Exception as exc:
            # dm_sql_referenced_entities raises if the object doesn't compile
            result["error"] = f"References query failed: {exc}"

        # Inbound — what references this object
        try:
            cur.execute(_SQL_REFBY, (full_name,))
            result["referenced_by"] = [
                {
                    "schema_name": r[0] or "dbo",
                    "object_name": r[1] or "",
                    "object_type": _normalise_type(r[2] or ""),
                    "type_code":   r[3] or "",
                }
                for r in cur.fetchall()
            ]
        except Exception as exc:
            existing_err = result.get("error", "")
            result["error"] = (existing_err + " | " if existing_err else "") + f"RefBy query failed: {exc}"

        conn.close()
    except Exception as exc:
        result["error"] = str(exc)
        log.warning("get_dependencies_live failed for %s: %s", full_name, exc)

    return result


# ── Schema-store (offline) dependency inference ───────────────────────────────

def get_dependencies_from_schema_store(
    object_name: str,
    schema_name: str = "dbo",
    db_registry_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Infer object dependencies by parsing source definitions in the
    schema_objects vector store.  No live database connection required.

    Limitations:
    - Can only detect references to objects that are themselves in the store.
    - Uses simple text matching — may miss dynamically constructed names.
    """
    result: Dict[str, Any] = {"references": [], "referenced_by": [], "error": ""}

    try:
        from dbanalyser.schema_intel.repository import list_schema_objects
        all_objs = list_schema_objects(db_registry_id=db_registry_id, limit=5000)

        # Find target object
        target = next(
            (o for o in all_objs
             if o.get("object_name", "").lower() == object_name.lower()
             and (not schema_name or o.get("schema_name", "").lower() == schema_name.lower())),
            None,
        )

        if not target:
            result["error"] = (
                f"Object '{schema_name}.{object_name}' not found in the schema store. "
                "Run `dbanalyser ingest` first."
            )
            return result

        source = (target.get("definition") or "").upper()

        # Outbound: find tables/views/procs referenced in this object's source
        references = []
        for obj in all_objs:
            name = obj.get("object_name", "")
            if not name or name.lower() == object_name.lower():
                continue
            if obj.get("object_type", "") in ("column",):
                continue
            # Check if the name appears as a word boundary in source
            if re.search(r'\b' + re.escape(name.upper()) + r'\b', source):
                references.append({
                    "schema_name": obj.get("schema_name", "dbo"),
                    "object_name": name,
                    "object_type": obj.get("object_type", "").title(),
                    "column_name": "",
                })
        result["references"] = _deduplicate(references, ("schema_name", "object_name"))

        # Inbound: find objects whose source mentions this object's name
        target_upper = object_name.upper()
        referenced_by = []
        for obj in all_objs:
            if obj.get("object_name", "").lower() == object_name.lower():
                continue
            if obj.get("object_type", "") in ("column",):
                continue
            obj_source = (obj.get("definition") or "").upper()
            if re.search(r'\b' + re.escape(target_upper) + r'\b', obj_source):
                referenced_by.append({
                    "schema_name": obj.get("schema_name", "dbo"),
                    "object_name": obj.get("object_name", ""),
                    "object_type": obj.get("object_type", "").title(),
                    "type_code":   "",
                })
        result["referenced_by"] = _deduplicate(referenced_by, ("schema_name", "object_name"))

    except Exception as exc:
        result["error"] = str(exc)
        log.warning("get_dependencies_from_schema_store failed: %s", exc)

    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_type(raw: str) -> str:
    _map = {
        "SQL_STORED_PROCEDURE": "Stored Procedure",
        "VIEW":                 "View",
        "USER_TABLE":           "Table",
        "OBJECT_OR_COLUMN":     "Object/Column",
        "SQL_SCALAR_FUNCTION":  "Scalar Function",
        "SQL_TABLE_VALUED_FUNCTION": "Table Function",
        "SQL_TRIGGER":          "Trigger",
        "SYNONYM":              "Synonym",
    }
    return _map.get(raw.upper(), raw.replace("_", " ").title())


def _deduplicate(items: List[dict], keys: tuple) -> List[dict]:
    seen: set = set()
    out: List[dict] = []
    for item in items:
        key = tuple(item.get(k, "") for k in keys)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def list_all_objects_in_store(
    db_registry_id: Optional[int] = None,
    exclude_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Return distinct objects from the schema store for UI dropdowns."""
    exclude_types = exclude_types or ["column", "index"]
    try:
        from dbanalyser.schema_intel.repository import list_schema_objects
        objs = list_schema_objects(db_registry_id=db_registry_id, limit=5000)
        result = []
        seen: set = set()
        for o in objs:
            ot = o.get("object_type", "")
            if ot.lower() in [e.lower() for e in exclude_types]:
                continue
            key = (o.get("schema_name", "dbo"), o.get("object_name", ""), ot)
            if key not in seen:
                seen.add(key)
                result.append({
                    "schema_name": o.get("schema_name", "dbo"),
                    "object_name": o.get("object_name", ""),
                    "object_type": ot,
                    "display":     f"{o.get('schema_name','dbo')}.{o.get('object_name','')} ({ot})",
                })
        return sorted(result, key=lambda x: (x["object_type"], x["object_name"]))
    except Exception as exc:
        log.warning("list_all_objects_in_store failed: %s", exc)
        return []
