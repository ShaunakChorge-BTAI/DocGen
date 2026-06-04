"""
Schema Semantic Searcher
========================
Uses cosine similarity over stored embeddings to find relevant schema objects
for a given query (object name, SQL snippet, or natural language question).

build_schema_context_for_object() is the key function called by the AI optimizer
to assemble schema context before sending a prompt to Claude.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .embedder import cosine_similarity, embed_schema_object

log = logging.getLogger(__name__)


def search_schema(
    query: str,
    db_registry_id: Optional[int] = None,
    top_k:          int = 10,
    min_score:      float = 0.10,
    object_types:   Optional[List[str]] = None,
    use_transformers: bool = False,
) -> List[Dict[str, Any]]:
    """
    Semantic search over the schema_objects table.

    Args:
        query          : free-form text — object name, SQL snippet, or question
        db_registry_id : restrict search to one database
        top_k          : maximum results to return
        min_score      : minimum cosine similarity threshold (0–1)
        object_types   : restrict to specific types (table, column, procedure, etc.)
        use_transformers: use sentence-transformers if available

    Returns:
        List of dicts sorted by similarity score (descending).
        Each dict has: object_type, schema_name, object_name, parent_name,
                       definition, similarity_score.
    """
    # Embed the query
    query_vec = embed_schema_object(
        object_type="query",
        object_name=query,
        definition=query,
        use_transformers=use_transformers,
    )

    # Load stored embeddings from DB
    from .repository import get_embeddings_for_db
    candidates = get_embeddings_for_db(db_registry_id)

    if not candidates:
        log.debug("No schema embeddings found for db_registry_id=%s", db_registry_id)
        return []

    # Filter by object type if requested
    if object_types:
        ot_lower = [t.lower() for t in object_types]
        candidates = [c for c in candidates if c.get("object_type", "").lower() in ot_lower]

    # Score and rank
    scored = []
    for obj in candidates:
        vec = obj.get("embedding")
        if vec is None:
            continue
        score = cosine_similarity(query_vec, vec)
        if score >= min_score:
            scored.append({
                "object_type":     obj["object_type"],
                "schema_name":     obj["schema_name"],
                "object_name":     obj["object_name"],
                "parent_name":     obj.get("parent_name", ""),
                "definition":      (obj.get("definition", "") or "")[:300],
                "similarity_score": round(score, 4),
            })

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:top_k]


def build_schema_context_for_object(
    sql_object_name: str,
    source_sql:      str,
    db_registry_id:  Optional[int] = None,
    max_tables:      int = 8,
    max_columns:     int = 40,
    use_transformers: bool = False,
) -> str:
    """
    Build a concise schema context string for the AI optimizer.

    Finds tables referenced in source_sql, fetches their columns,
    and formats everything as a readable DDL snippet.

    IMPORTANT (enforced by CLAUDE.md):
      - This MUST be called before every AI optimization call.
      - Never pass SQL to the AI optimizer without first calling this function.

    Args:
        sql_object_name: name of the procedure/view being optimized
        source_sql      : full SQL source to analyse
        db_registry_id  : which DB's schema to use
        max_tables      : cap on referenced tables to include
        max_columns     : cap on total columns to include

    Returns:
        A formatted string like:
          ## Schema Context for usp_ProcessPayment
          ### Tables Referenced
          dbo.Accounts (table)
            - AccountId   int  NOT NULL  PK
            - Balance     decimal(18,2)  NOT NULL
          ...
    """
    if not db_registry_id:
        # Try to search by object name alone
        results = search_schema(
            query=sql_object_name, db_registry_id=None,
            top_k=max_tables, object_types=["table", "view"],
            use_transformers=use_transformers,
        )
    else:
        # Combined query: object name + first 200 chars of SQL
        query = f"{sql_object_name} {source_sql[:200]}"
        results = search_schema(
            query=query, db_registry_id=db_registry_id,
            top_k=max_tables, object_types=["table", "view"],
            use_transformers=use_transformers,
        )

    if not results:
        return f"## Schema Context\n*No schema information available for {sql_object_name}.*\n"

    lines = [f"## Schema Context for {sql_object_name}"]
    col_count = 0

    for tbl in results[:max_tables]:
        tbl_name = f"{tbl['schema_name']}.{tbl['object_name']}"
        lines.append(f"\n### {tbl_name} ({tbl['object_type']})")

        # Fetch columns for this table
        col_results = search_schema(
            query=tbl["object_name"],
            db_registry_id=db_registry_id,
            top_k=30,
            min_score=0.0,
            object_types=["column"],
            use_transformers=use_transformers,
        )
        col_results = [c for c in col_results if c.get("parent_name") == tbl["object_name"]]

        if col_results:
            for col in col_results[:max_columns - col_count]:
                flags = []
                pk_flag = "(PK)" if col.get("definition", "").lower().count("pk") else ""
                fk_flag = "(FK)" if col.get("definition", "").lower().count("fk") else ""
                col_count += 1
                lines.append(f"  - {col['object_name']}  {col.get('definition','')}"
                              f"  {pk_flag}{fk_flag}")
        else:
            lines.append(f"  (columns not available in schema store)")

        if col_count >= max_columns:
            lines.append("  ... (truncated)")
            break

    return "\n".join(lines)
