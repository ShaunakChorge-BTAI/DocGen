"""PostgreSQL persistence for schema objects + embeddings."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .embedder import embed_schema_object, vector_to_json, vector_from_json
from .extractor import SchemaObject

log = logging.getLogger(__name__)


def upsert_schema_object(
    db_registry_id: Optional[int],
    obj: SchemaObject,
    use_transformers: bool = False,
) -> int:
    """
    Insert or update a schema object and its embedding.
    Returns the row id (-1 on error).
    """
    vec = embed_schema_object(
        object_type=obj.object_type,
        object_name=obj.object_name,
        parent_name=obj.parent_name,
        definition=obj.definition,
        use_transformers=use_transformers,
    )
    embedding_json = vector_to_json(vec)

    try:
        from dbanalyser.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO schema_objects
                    (db_registry_id, object_type, schema_name, object_name,
                     parent_name, data_type, is_nullable, is_primary_key,
                     is_foreign_key, definition, embedding_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (db_registry_id, object_type, schema_name, object_name, parent_name)
                DO UPDATE SET
                    data_type      = EXCLUDED.data_type,
                    is_nullable    = EXCLUDED.is_nullable,
                    is_primary_key = EXCLUDED.is_primary_key,
                    is_foreign_key = EXCLUDED.is_foreign_key,
                    definition     = EXCLUDED.definition,
                    embedding_json = EXCLUDED.embedding_json,
                    ingested_at    = NOW()
                RETURNING id
            """, (
                db_registry_id,
                obj.object_type, obj.schema_name, obj.object_name,
                obj.parent_name or "",
                obj.data_type,
                obj.is_nullable, obj.is_primary_key, obj.is_foreign_key,
                (obj.definition or "").replace("\x00", "")[:4000],
                embedding_json,
            ))
            row = cur.fetchone()
            return int(row["id"]) if row else -1
    except Exception as exc:
        log.error("upsert_schema_object failed: %s", exc)
        return -1


def list_schema_objects(
    db_registry_id: Optional[int] = None,
    object_type:    Optional[str] = None,
    limit:          int = 500,
) -> List[Dict[str, Any]]:
    """Return schema objects, optionally filtered by db_registry_id or type."""
    try:
        from dbanalyser.db.connection import get_cursor
        wheres = []
        params: list = []
        if db_registry_id is not None:
            wheres.append("db_registry_id = %s"); params.append(db_registry_id)
        if object_type:
            wheres.append("object_type = %s"); params.append(object_type)
        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        params.append(limit)
        with get_cursor() as cur:
            cur.execute(f"""
                SELECT id, db_registry_id, object_type, schema_name,
                       object_name, parent_name, data_type, is_nullable,
                       is_primary_key, is_foreign_key, definition, ingested_at
                FROM schema_objects
                {where_clause}
                ORDER BY object_type, schema_name, object_name
                LIMIT %s
            """, params)
            return list(cur.fetchall() or [])
    except Exception as exc:
        log.warning("list_schema_objects failed: %s", exc)
        return []


def get_schema_summary(db_registry_id: Optional[int] = None) -> Dict[str, Any]:
    """Return counts of schema objects per type."""
    try:
        from dbanalyser.db.connection import get_cursor
        where = "WHERE db_registry_id = %s" if db_registry_id is not None else ""
        params = [db_registry_id] if db_registry_id is not None else []
        with get_cursor() as cur:
            cur.execute(f"""
                SELECT object_type, COUNT(*) AS cnt
                FROM schema_objects
                {where}
                GROUP BY object_type
                ORDER BY cnt DESC
            """, params)
            rows = cur.fetchall() or []
            return {r["object_type"]: r["cnt"] for r in rows}
    except Exception as exc:
        log.warning("get_schema_summary failed: %s", exc)
        return {}


def get_embeddings_for_db(db_registry_id: Optional[int]) -> List[Dict[str, Any]]:
    """Fetch all schema objects with their embeddings for a given DB."""
    try:
        from dbanalyser.db.connection import get_cursor
        where = "WHERE db_registry_id = %s" if db_registry_id is not None else ""
        params = [db_registry_id] if db_registry_id is not None else []
        with get_cursor() as cur:
            cur.execute(f"""
                SELECT id, object_type, schema_name, object_name,
                       parent_name, definition, embedding_json
                FROM schema_objects
                {where}
                ORDER BY object_type, object_name
            """, params)
            rows = cur.fetchall() or []
            result = []
            for r in rows:
                d = dict(r)
                if d.get("embedding_json"):
                    d["embedding"] = vector_from_json(d["embedding_json"])
                del d["embedding_json"]
                result.append(d)
            return result
    except Exception as exc:
        log.warning("get_embeddings_for_db failed: %s", exc)
        return []


def delete_schema_for_db(db_registry_id: int) -> int:
    """Delete all schema objects for a given database. Returns rows deleted."""
    try:
        from dbanalyser.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM schema_objects WHERE db_registry_id = %s", (db_registry_id,)
            )
            return cur.rowcount or 0
    except Exception as exc:
        log.error("delete_schema_for_db failed: %s", exc)
        return 0
