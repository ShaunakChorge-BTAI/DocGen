"""
Optimization Context Builder
==============================
Assembles all context needed for AI optimization:
  1. Schema context (from schema_intel)
  2. Rule findings for the object
  3. Execution plan (if available)
  4. Historical optimization context (last N optimizations for this object)

ENFORCED BY CLAUDE.md:
  - build_optimization_context() MUST be called before optimize_sql_object()
  - Schema context must be non-empty or optimization should be declined
  - Execution plan should always be included when available
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def build_optimization_context(
    object_name:    str,
    source_sql:     str,
    db_registry_id: Optional[int] = None,
    findings:       Optional[List[dict]] = None,
    execution_plan: str = "",
    use_transformers: bool = False,
) -> dict:
    """
    Build the full optimization context for a SQL object.

    Returns a dict with keys:
      - schema_context (str)   : formatted schema DDL
      - findings       (list)  : rule findings for this object
      - execution_plan (str)   : execution plan text
      - context_quality (str)  : "good" | "partial" | "none"
      - warnings        (list) : any context warnings

    Usage::

        ctx = build_optimization_context("usp_Process", sql, db_registry_id=42)
        result = optimize_sql_object(
            object_name=...,
            source_sql=sql,
            schema_context=ctx["schema_context"],
            findings=ctx["findings"],
            execution_plan=ctx["execution_plan"],
        )
    """
    warnings: List[str] = []
    schema_context = ""

    # ── 1. Fetch schema context ───────────────────────────────────────────────
    try:
        from dbanalyser.schema_intel.searcher import build_schema_context_for_object
        schema_context = build_schema_context_for_object(
            sql_object_name=object_name,
            source_sql=source_sql,
            db_registry_id=db_registry_id,
            use_transformers=use_transformers,
        )
        if "not available" in schema_context.lower() or len(schema_context) < 60:
            warnings.append(
                "Schema context is thin. Run `dbanalyser ingest` to load schema into the "
                "knowledge base for better optimization quality."
            )
    except Exception as exc:
        schema_context = f"## Schema Context\n*Schema retrieval failed: {exc}*"
        warnings.append(f"Schema retrieval error: {exc}")
        log.warning("Schema context retrieval failed for %s: %s", object_name, exc)

    # ── 2. Execution plan context ─────────────────────────────────────────────
    if not execution_plan:
        warnings.append(
            "No execution plan provided. Include execution plan for better "
            "performance optimization. Capture with: SET STATISTICS XML ON"
        )

    # ── 3. Findings context ───────────────────────────────────────────────────
    obj_findings = list(findings or [])
    if not obj_findings:
        warnings.append(
            "No rule findings provided. Run `dbanalyser run` first so the AI optimizer "
            "knows which issues to prioritize."
        )

    # ── 4. Determine context quality ──────────────────────────────────────────
    has_schema  = bool(schema_context) and "not available" not in schema_context
    has_plan    = bool(execution_plan)
    has_findings = bool(obj_findings)

    if has_schema and has_plan and has_findings:
        quality = "good"
    elif has_schema or has_findings:
        quality = "partial"
    else:
        quality = "none"

    return {
        "schema_context":  schema_context,
        "findings":        obj_findings,
        "execution_plan":  execution_plan,
        "context_quality": quality,
        "warnings":        warnings,
    }


def get_recent_optimizations(
    object_name:    str,
    db_registry_id: Optional[int] = None,
    limit:          int = 5,
) -> List[Dict[str, Any]]:
    """Fetch recent AI optimizations for a specific object (for context/history)."""
    try:
        from dbanalyser.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, object_name, confidence_score, model_used,
                       tokens_used, created_at,
                       LEFT(reasoning, 300) AS reasoning_preview
                FROM ai_optimizations
                WHERE object_name = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (object_name, limit))
            return list(cur.fetchall() or [])
    except Exception as exc:
        log.warning("get_recent_optimizations failed: %s", exc)
        return []
