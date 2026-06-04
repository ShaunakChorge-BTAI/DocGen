"""
DBAnalyser — Repository layer.
All SQL reads and writes against the PostgreSQL results database.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import psycopg2.extras

from dbanalyser.db.connection import get_conn, get_cursor
from dbanalyser.db.models import (
    DbRegistry, DmvSnapshot, Finding, HealthTrend,
    ObjectSnapshot, Run, health_score,
)

logger = logging.getLogger(__name__)


# ─── DbRegistry ──────────────────────────────────────────────────────────────

def upsert_db_registry(db: DbRegistry, org_id: Optional[int] = None) -> int:
    """Insert or update a database registry entry. Returns the integer id."""
    # Upsert via SELECT + UPDATE/INSERT (avoids ON CONFLICT constraint issues
    # after Phase G removed the global unique constraint on name)
    params = {
        "name":              db.name,
        "db_type":           db.db_type,
        "environment":       db.environment,
        "host":              db.host,
        "port":              db.port,
        "database_name":     db.database_name,
        "connection_string": db.connection_string,
        "use_windows_auth":  db.use_windows_auth,
        "username":          db.username,
        "password":          db.password,
        "description":       db.description,
        "owner_label":       db.owner_label,
        "tags":              db.tags,
        "is_active":         db.is_active,
        "org_id":            org_id or getattr(db, "org_id", None),
    }
    with get_conn() as conn:
        cur = conn.cursor()
        existing = None
        
        # If ID is explicitly provided, use it directly (for edits)
        if getattr(db, 'id', None):
            cur.execute("SELECT id FROM db_registry WHERE id=%s", (db.id,))
            existing = cur.fetchone()
        else:
            # Try to find existing row — match on name + host + port so the same
            # physical server is never registered twice under the same org.
            if params["org_id"] is not None:
                cur.execute(
                    "SELECT id FROM db_registry WHERE org_id=%s AND name=%s AND host=%s AND port=%s",
                    (params["org_id"], params["name"], params["host"], params["port"]),
                )
            else:
                cur.execute(
                    "SELECT id FROM db_registry WHERE name=%s AND host=%s AND port=%s AND org_id IS NULL",
                    (params["name"], params["host"], params["port"]),
                )
            existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE db_registry SET
                    name=%s, db_type=%s, environment=%s, host=%s, port=%s, database_name=%s,
                    connection_string=%s, use_windows_auth=%s, username=%s, password=%s,
                    description=%s, owner_label=%s, tags=%s, is_active=%s, updated_at=NOW()
                WHERE id=%s RETURNING id
            """, (params["name"], params["db_type"], params["environment"], params["host"], params["port"],
                  params["database_name"], params["connection_string"],
                  params["use_windows_auth"], params["username"], params["password"],
                  params["description"], params["owner_label"],
                  params["tags"], params["is_active"], existing[0]))
        else:
            cur.execute("""
                INSERT INTO db_registry (
                    org_id, name, db_type, environment, host, port, database_name,
                    connection_string, use_windows_auth, username, password,
                    description, owner_label, tags, is_active
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (params["org_id"], params["name"], params["db_type"], params["environment"],
                  params["host"], params["port"], params["database_name"],
                  params["connection_string"], params["use_windows_auth"],
                  params["username"], params["password"], params["description"],
                  params["owner_label"], params["tags"], params["is_active"]))
        row = cur.fetchone()
        return row[0]


def get_db_registry(name: str) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM db_registry WHERE name = %s", (name,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_db_registry_by_id(id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM db_registry WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_db_registries(active_only: bool = False) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        sql = "SELECT * FROM db_registry"
        if active_only:
            sql += " WHERE is_active = TRUE"
        sql += " ORDER BY environment, name"
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def update_db_registry_last_run(db_id: int, health: float) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE db_registry
               SET last_run_at = NOW(), last_health = %s, updated_at = NOW()
             WHERE id = %s
        """, (health, db_id))


# def delete_db_registry(db_identifier: Union[int, str]) -> bool:
#     """Soft-delete (set is_active=False) by id or exact name. Returns True if found."""
#     if isinstance(db_identifier, int):
#         where_clause = "id = %s"
#     else:
#         where_clause = "name = %s"

#     with get_conn() as conn, conn.cursor() as cur:
#         cur.execute(f"""
#             UPDATE db_registry SET is_active = FALSE, updated_at = NOW()
#              WHERE {where_clause}
#         """, (db_identifier,))
#         return cur.rowcount > 0
def delete_db_registry(identifier) -> bool:
    """Soft-delete (set is_active=False). Accepts int (ID) or str (Name)."""
    from dbanalyser.db.connection import get_conn
    with get_conn() as conn, conn.cursor() as cur:
        if str(identifier).isdigit():
            # Frontend sent an ID
            cur.execute("""
                UPDATE db_registry SET is_active = FALSE, updated_at = NOW()
                 WHERE id = %s
            """, (int(identifier),))
        else:
            # Frontend sent a String Name
            cur.execute("""
                UPDATE db_registry SET is_active = FALSE, updated_at = NOW()
                 WHERE name = %s
            """, (str(identifier),))
        return cur.rowcount > 0



def hard_delete_db_registry(db_registry_id: int) -> Dict[str, int]:
    """
    Hard delete: Permanently remove database registry and ALL associated scan data.

    Cascade deletion order:
      1. findings (depends on runs.id)
      2. object_snapshots (depends on runs.id)
      3. health_trend (depends on runs.id)
      4. pipeline_steps (depends on runs.id)
      5. runs (depends on db_registry.id)
      6. db_registry

    Returns dict with deletion counts: {findings, snapshots, health_trend, pipeline_steps, runs, db_registry}
    """
    counts = {}
    with get_conn() as conn:
        cur = conn.cursor()

        try:
            # Get all run IDs for this database
            cur.execute("SELECT id FROM runs WHERE db_registry_id = %s", (db_registry_id,))
            run_ids = [r[0] for r in cur.fetchall()]

            # Delete findings
            if run_ids:
                placeholders = ",".join(["%s"] * len(run_ids))
                cur.execute(f"DELETE FROM findings WHERE run_id IN ({placeholders})", run_ids)
                counts["findings"] = cur.rowcount

            # Delete object_snapshots
            if run_ids:
                cur.execute(f"DELETE FROM object_snapshots WHERE run_id IN ({placeholders})", run_ids)
                counts["snapshots"] = cur.rowcount

            # Delete health_trend
            if run_ids:
                cur.execute(f"DELETE FROM health_trend WHERE run_id IN ({placeholders})", run_ids)
                counts["health_trend"] = cur.rowcount

            # Delete pipeline_steps
            if run_ids:
                cur.execute(f"DELETE FROM pipeline_steps WHERE run_id IN ({placeholders})", run_ids)
                counts["pipeline_steps"] = cur.rowcount

            # Delete runs
            cur.execute("DELETE FROM runs WHERE db_registry_id = %s", (db_registry_id,))
            counts["runs"] = cur.rowcount

            # Delete db_registry
            cur.execute("DELETE FROM db_registry WHERE id = %s", (db_registry_id,))
            counts["db_registry"] = cur.rowcount

            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise exc

    return counts


def hard_delete_run(run_id: int) -> Dict[str, int]:
    """
    Hard delete: Permanently remove a single run and its associated data.

    Cascade deletion order:
      1. findings
      2. object_snapshots
      3. health_trend
      4. pipeline_steps
      5. runs

    Returns dict with deletion counts.
    """
    counts = {}
    with get_conn() as conn:
        cur = conn.cursor()

        try:
            # Delete findings
            cur.execute("DELETE FROM findings WHERE run_id = %s", (run_id,))
            counts["findings"] = cur.rowcount

            # Delete object_snapshots
            cur.execute("DELETE FROM object_snapshots WHERE run_id = %s", (run_id,))
            counts["snapshots"] = cur.rowcount

            # Delete health_trend
            cur.execute("DELETE FROM health_trend WHERE run_id = %s", (run_id,))
            counts["health_trend"] = cur.rowcount

            # Delete pipeline_steps
            cur.execute("DELETE FROM pipeline_steps WHERE run_id = %s", (run_id,))
            counts["pipeline_steps"] = cur.rowcount

            # Delete run
            cur.execute("DELETE FROM runs WHERE id = %s", (run_id,))
            counts["runs"] = cur.rowcount

            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise exc

    return counts


# ─── Run ─────────────────────────────────────────────────────────────────────

def insert_run(run: Run) -> int:
    """Insert a run record. Returns the integer auto-increment id."""
    sql = """
    INSERT INTO runs (
        run_id, label, db_registry_id, environment, source_mode, config_hash,
        file_input_path, database_name, host, duration_sec,
        total_objects, total_issues, critical_count, high_count,
        medium_count, low_count, health_score, status, notes
    ) VALUES (
        %(run_id)s, %(label)s, %(db_registry_id)s, %(environment)s,
        %(source_mode)s, %(config_hash)s,
        %(file_input_path)s, %(database_name)s, %(host)s, %(duration_sec)s,
        %(total_objects)s, %(total_issues)s, %(critical_count)s, %(high_count)s,
        %(medium_count)s, %(low_count)s, %(health_score)s, %(status)s, %(notes)s
    )
    ON CONFLICT (run_id) DO UPDATE SET
        duration_sec   = EXCLUDED.duration_sec,
        total_objects  = EXCLUDED.total_objects,
        total_issues   = EXCLUDED.total_issues,
        critical_count = EXCLUDED.critical_count,
        high_count     = EXCLUDED.high_count,
        medium_count   = EXCLUDED.medium_count,
        low_count      = EXCLUDED.low_count,
        health_score   = EXCLUDED.health_score,
        status         = EXCLUDED.status
    RETURNING id
    """
    params = {
        "run_id":          run.run_id,
        "label":           run.label,
        "db_registry_id":  run.db_registry_id,
        "environment":     run.environment,
        "source_mode":     run.source_mode,
        "config_hash":     run.config_hash,
        "file_input_path": run.file_input_path,
        "database_name":   run.database_name,
        "host":            run.host,
        "duration_sec":    run.duration_sec,
        "total_objects":   run.total_objects,
        "total_issues":    run.total_issues,
        "critical_count":  run.critical_count,
        "high_count":      run.high_count,
        "medium_count":    run.medium_count,
        "low_count":       run.low_count,
        "health_score":    run.health_score,
        "status":          run.status,
        "notes":           run.notes,
    }
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0]


def update_run_counts(run_id: int, duration_sec: float,
                      total_objects: int, total_issues: int,
                      critical: int, high: int, medium: int, low: int,
                      score: float) -> None:
    sql = """
    UPDATE runs SET
        duration_sec   = %(dur)s,
        total_objects  = %(obj)s,
        total_issues   = %(iss)s,
        critical_count = %(crit)s,
        high_count     = %(high)s,
        medium_count   = %(med)s,
        low_count      = %(low)s,
        health_score   = %(score)s
    WHERE id = %(run_id)s
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, dict(run_id=run_id, dur=duration_sec, obj=total_objects,
                              iss=total_issues, crit=critical, high=high,
                              med=medium, low=low, score=score))


def get_run(run_id: Optional[int] = None,
            run_uuid: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch a run by integer id or UUID string. If both None, returns latest."""
    with get_cursor() as cur:
        if run_id is not None:
            cur.execute("SELECT * FROM runs WHERE id = %s", (run_id,))
        elif run_uuid:
            cur.execute("SELECT * FROM runs WHERE run_id = %s", (run_uuid,))
        else:
            cur.execute("SELECT * FROM runs ORDER BY timestamp DESC LIMIT 1")
        row = cur.fetchone()
        return dict(row) if row else None


def list_runs(limit: int = 50,
              db_registry_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        if db_registry_id is not None:
            cur.execute("""
                SELECT r.*, d.name AS db_name, d.environment AS db_env
                  FROM runs r
                  LEFT JOIN db_registry d ON d.id = r.db_registry_id
                 WHERE r.db_registry_id = %s
                 ORDER BY r.timestamp DESC LIMIT %s
            """, (db_registry_id, limit))
        else:
            cur.execute("""
                SELECT r.*, d.name AS db_name, d.environment AS db_env
                  FROM runs r
                  LEFT JOIN db_registry d ON d.id = r.db_registry_id
                 ORDER BY r.timestamp DESC LIMIT %s
            """, (limit,))
        return [dict(r) for r in cur.fetchall()]


# ─── ObjectSnapshot ──────────────────────────────────────────────────────────

def bulk_insert_snapshots(snapshots: List[ObjectSnapshot]) -> None:
    if not snapshots:
        return
    rows = [
        (s.run_id, s.object_name, s.object_type, s.schema_name,
         s.file_path, s.content_hash, s.lines, s.size_kb,
         s.risk_score, s.risk_level, s.issue_count, s.critical_count,
         s.high_count, s.source, s.content_drift)
        for s in snapshots
    ]
    sql = """
    INSERT INTO object_snapshots (
        run_id, object_name, object_type, schema_name,
        file_path, content_hash, lines, size_kb,
        risk_score, risk_level, issue_count, critical_count,
        high_count, source, content_drift
    ) VALUES %s
    """
    with get_conn() as conn:
        psycopg2.extras.execute_values(conn.cursor(), sql, rows, page_size=500)


def get_object_history(object_name: str, limit: int = 20,
                       db_registry_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        if db_registry_id is not None:
            cur.execute("""
                SELECT s.*, r.timestamp, r.environment, r.label
                  FROM object_snapshots s
                  JOIN runs r ON r.id = s.run_id
                 WHERE s.object_name = %s AND r.db_registry_id = %s
                 ORDER BY r.timestamp DESC LIMIT %s
            """, (object_name, db_registry_id, limit))
        else:
            cur.execute("""
                SELECT s.*, r.timestamp, r.environment, r.label
                  FROM object_snapshots s
                  JOIN runs r ON r.id = s.run_id
                 WHERE s.object_name = %s
                 ORDER BY r.timestamp DESC LIMIT %s
            """, (object_name, limit))
        return [dict(r) for r in cur.fetchall()]


# ─── Findings ────────────────────────────────────────────────────────────────

def bulk_insert_findings(run_int_id: int, findings: List[Finding]) -> None:
    if not findings:
        return
    logger.debug(
        "bulk_insert_findings called for run_int_id=%s with %s findings",
        run_int_id,
        len(findings),
    )
    if findings:
        first = findings[0]
        logger.debug(
            "First finding: %s, status=%s",
            first.object_name,
            repr(first.status),
        )

    rows = [
        (run_int_id, f.object_name, f.object_type, f.schema_name,
         f.category, f.issue, f.severity, f.line_number,
         f.recommendation, f.snippet, f.rule_id,
         'Open',  # Always use 'Open' as status for new findings
         f.first_seen_run, f.last_seen_run,
         f.is_new, f.is_regression, f.jira_ticket, f.notes)
        for f in findings
    ]
    sql = """
    INSERT INTO findings (
        run_id, object_name, object_type, schema_name,
        category, issue, severity, line_number,
        recommendation, snippet, rule_id,
        status, first_seen_run, last_seen_run,
        is_new, is_regression, jira_ticket, notes
    ) VALUES %s
    """
    with get_conn() as conn:
        psycopg2.extras.execute_values(conn.cursor(), sql, rows, page_size=500)


def get_findings(run_int_id: int,
                 severity: Optional[str] = None,
                 category: Optional[str] = None,
                 status:   Optional[str] = None,
                 limit:    int = 5000):
    """Return findings as a list of dicts (or DataFrame if pandas available)."""
    conditions = ["run_id = %(run_id)s"]
    params: Dict[str, Any] = {"run_id": run_int_id, "limit": limit}
    if severity:
        conditions.append("severity = %(severity)s")
        params["severity"] = severity
    if category:
        conditions.append("category = %(category)s")
        params["category"] = category
    if status:
        conditions.append("status = %(status)s")
        params["status"] = status
    where = " AND ".join(conditions)
    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM findings WHERE {where} "
            f"ORDER BY severity, object_name LIMIT %(limit)s",
            params)
        rows = [dict(r) for r in cur.fetchall()]
    try:
        import pandas as pd
        return pd.DataFrame(rows)
    except ImportError:
        return rows


def get_all_findings_for_db(db_registry_id: int,
                            run_id: Optional[int] = None,
                            limit: int = 10000):
    """Get findings across all runs for a given database (or latest run only)."""
    with get_cursor() as cur:
        if run_id:
            cur.execute("""
                SELECT f.*, r.label, r.timestamp
                  FROM findings f
                  JOIN runs r ON r.id = f.run_id
                 WHERE r.db_registry_id = %s AND f.run_id = %s
                 ORDER BY f.severity, f.object_name
                 LIMIT %s
            """, (db_registry_id, run_id, limit))
        else:
            # latest run for this DB
            cur.execute("""
                SELECT f.*, r.label, r.timestamp
                  FROM findings f
                  JOIN runs r ON r.id = f.run_id
                 WHERE r.id = (
                     SELECT id FROM runs
                      WHERE db_registry_id = %s
                      ORDER BY timestamp DESC LIMIT 1
                 )
                 ORDER BY f.severity, f.object_name
                 LIMIT %s
            """, (db_registry_id, limit))
        rows = [dict(r) for r in cur.fetchall()]
    try:
        import pandas as pd
        return pd.DataFrame(rows)
    except ImportError:
        return rows


def update_finding_status(finding_id: int, status: str,
                           user: str = "system",
                           reason: Optional[str] = None,
                           jira: Optional[str] = None) -> None:
    now = datetime.utcnow()
    sql = "UPDATE findings SET status = %(status)s, updated_at = %(now)s"
    params: Dict[str, Any] = {"id": finding_id, "status": status, "now": now}
    if status == "acknowledged":
        sql += ", acknowledged_by = %(user)s, acknowledged_at = %(now)s"
        params["user"] = user
    elif status in ("fixed", "wontfix"):
        sql += ", fixed_at = %(now)s"
    elif status == "suppressed":
        sql += ", suppressed_by = %(user)s, suppressed_at = %(now)s, suppress_reason = %(reason)s"
        params.update({"user": user, "reason": reason})
    if jira:
        sql += ", jira_ticket = %(jira)s"
        params["jira"] = jira
    sql += " WHERE id = %(id)s"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)


def get_new_vs_resolved(run_int_id: int,
                        prev_run_int_id: Optional[int]) -> Dict[str, int]:
    if not prev_run_int_id:
        return {"new": 0, "resolved": 0, "regressed": 0}
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE f.is_new)        AS new,
                COUNT(*) FILTER (WHERE f.is_regression) AS regressed
            FROM findings f WHERE f.run_id = %s
        """, (run_int_id,))
        row = dict(cur.fetchone())
        cur.execute("""
            SELECT COUNT(*) AS resolved
            FROM findings prev
            WHERE prev.run_id = %s
              AND prev.status = 'open'
              AND NOT EXISTS (
                  SELECT 1 FROM findings cur
                  WHERE cur.run_id = %s
                    AND cur.object_name = prev.object_name
                    AND cur.issue = prev.issue
              )
        """, (prev_run_int_id, run_int_id))
        row["resolved"] = cur.fetchone()["resolved"]
    return row


# ─── DMV Snapshots ────────────────────────────────────────────────────────────

def insert_dmv_snapshot(snap: DmvSnapshot) -> None:
    sql = """
    INSERT INTO dmv_snapshots (run_id, dmv_type, data_json, row_count)
    VALUES (%s, %s, %s, %s)
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (snap.run_id, snap.dmv_type,
                          json.dumps(snap.data_json), snap.row_count))


def get_dmv_snapshot(run_int_id: int, dmv_type: str) -> Optional[List[Dict]]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT data_json FROM dmv_snapshots WHERE run_id=%s AND dmv_type=%s",
            (run_int_id, dmv_type))
        row = cur.fetchone()
        return row["data_json"] if row else None


# ─── Health Trend ─────────────────────────────────────────────────────────────

def upsert_health_trend(trend: HealthTrend) -> None:
    sql = """
    INSERT INTO health_trend (
        run_id, db_registry_id, db_name, environment, timestamp,
        health_score, total_objects, total_issues,
        critical_count, high_count, medium_count, low_count,
        new_issues, resolved_issues
    ) VALUES (
        %(run_id)s, %(db_registry_id)s, %(db_name)s, %(environment)s, %(timestamp)s,
        %(health_score)s, %(total_objects)s, %(total_issues)s,
        %(critical_count)s, %(high_count)s, %(medium_count)s, %(low_count)s,
        %(new_issues)s, %(resolved_issues)s
    )
    ON CONFLICT (run_id) DO UPDATE SET
        health_score    = EXCLUDED.health_score,
        total_issues    = EXCLUDED.total_issues,
        new_issues      = EXCLUDED.new_issues,
        resolved_issues = EXCLUDED.resolved_issues
    """
    params = {
        "run_id":          trend.run_id,
        "db_registry_id":  trend.db_registry_id,
        "db_name":         trend.db_name,
        "environment":     trend.environment,
        "timestamp":       trend.timestamp or datetime.utcnow(),
        "health_score":    trend.health_score,
        "total_objects":   trend.total_objects,
        "total_issues":    trend.total_issues,
        "critical_count":  trend.critical_count,
        "high_count":      trend.high_count,
        "medium_count":    trend.medium_count,
        "low_count":       trend.low_count,
        "new_issues":      trend.new_issues,
        "resolved_issues": trend.resolved_issues,
    }
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)


def get_trend_for_db(db_registry_id: int, limit: int = 60):
    """Return trend rows for a specific database (newest first → chart reverses)."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM health_trend
             WHERE db_registry_id = %s
             ORDER BY timestamp DESC LIMIT %s
        """, (db_registry_id, limit))
        rows = [dict(r) for r in cur.fetchall()]
    try:
        import pandas as pd
        return pd.DataFrame(rows)
    except ImportError:
        return rows


def get_trend_all_dbs(limit_per_db: int = 30):
    """Latest N rows per database — useful for sparklines on the overview page."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT t.*, d.name AS db_name_label, d.environment, d.owner_label
              FROM health_trend t
              JOIN db_registry d ON d.id = t.db_registry_id
             WHERE t.id IN (
                 SELECT DISTINCT ON (db_registry_id)
                        id
                   FROM health_trend
                  ORDER BY db_registry_id, timestamp DESC
             )
             ORDER BY t.health_score ASC
        """)
        rows = [dict(r) for r in cur.fetchall()]
    try:
        import pandas as pd
        return pd.DataFrame(rows)
    except ImportError:
        return rows


# ─── AI Optimizations ────────────────────────────────────────────────────────

def insert_ai_optimization(
    object_name:         str,
    original_sql:        str,
    optimized_sql:       str,
    reasoning:           str,
    schema_context_used: str,
    execution_plan_used: str,
    findings_used:       list,
    confidence_score:    float,
    model_used:          str,
    tokens_used:         int,
    run_id:              Optional[int] = None,
    db_registry_id:      Optional[int] = None,
) -> int:
    """Insert one AI optimization record. Returns row id (-1 on error)."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ai_optimizations (
                    run_id, db_registry_id, object_name, original_sql,
                    optimized_sql, reasoning, schema_context_used,
                    execution_plan_used, findings_used, confidence_score,
                    model_used, tokens_used
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                RETURNING id
            """, (
                run_id, db_registry_id, object_name, original_sql,
                optimized_sql, reasoning, schema_context_used,
                execution_plan_used, json.dumps(findings_used),
                confidence_score, model_used, tokens_used,
            ))
            row = cur.fetchone()
            return int(row[0]) if row else -1
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("insert_ai_optimization failed: %s", exc)
        return -1


def get_ai_optimizations(
    object_name:    Optional[str] = None,
    db_registry_id: Optional[int] = None,
    limit:          int = 50,
    offset:         int = 0,
) -> List[Dict[str, Any]]:
    """Fetch AI optimization history."""
    wheres: List[str] = []
    params: list = []
    if object_name:
        wheres.append("object_name ILIKE %s"); params.append(f"%{object_name}%")
    if db_registry_id is not None:
        wheres.append("db_registry_id = %s"); params.append(db_registry_id)
    where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
    params += [limit, offset]
    try:
        with get_cursor() as cur:
            cur.execute(f"""
                SELECT id, run_id, db_registry_id, object_name, original_sql,
                       optimized_sql, reasoning, confidence_score,
                       model_used, tokens_used, created_at
                FROM ai_optimizations
                {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params)
            return [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("get_ai_optimizations failed: %s", exc)
        return []


def count_ai_optimizations(
    object_name:    Optional[str] = None,
    db_registry_id: Optional[int] = None,
) -> int:
    wheres: List[str] = []
    params: list = []
    if object_name:
        wheres.append("object_name ILIKE %s"); params.append(f"%{object_name}%")
    if db_registry_id is not None:
        wheres.append("db_registry_id = %s"); params.append(db_registry_id)
    where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
    try:
        with get_cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM ai_optimizations {where_sql}", params)
            row = cur.fetchone()
            return int(row["cnt"]) if row else 0
    except Exception:
        return 0


# ─── Pipeline Steps ───────────────────────────────────────────────────────────

def insert_pipeline_step(
    run_id:      int,
    step:        str,
    status:      str = "pending",
    details:     Optional[dict] = None,
) -> int:
    """Insert a pipeline step record. Returns row id (-1 on error)."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pipeline_steps (run_id, step, status, details)
                VALUES (%s, %s, %s, %s::jsonb)
                RETURNING id
            """, (run_id, step, status, json.dumps(details or {})))
            row = cur.fetchone()
            return int(row[0]) if row else -1
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("insert_pipeline_step failed: %s", exc)
        return -1


def update_pipeline_step(
    step_id:      int,
    status:       str,
    error:        Optional[str] = None,
    details:      Optional[dict] = None,
    duration_sec: Optional[float] = None,
) -> None:
    try:
        parts = ["status = %s", "completed_at = NOW()"]
        params: list = [status]
        if error is not None:
            parts.append("error = %s"); params.append(error)
        if details is not None:
            parts.append("details = %s::jsonb"); params.append(json.dumps(details))
        if duration_sec is not None:
            parts.append("duration_sec = %s"); params.append(duration_sec)
        params.append(step_id)
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE pipeline_steps SET {', '.join(parts)} WHERE id = %s", params
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("update_pipeline_step failed: %s", exc)


def get_pipeline_steps(run_id: int) -> List[Dict[str, Any]]:
    """Return all pipeline steps for a run, ordered by id."""
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, run_id, step, status, started_at, completed_at,
                       duration_sec, error, details
                FROM pipeline_steps
                WHERE run_id = %s
                ORDER BY id ASC
            """, (run_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("get_pipeline_steps failed: %s", exc)
        return []


# ─── Content Drift Detection ──────────────────────────────────────────────────

def detect_and_mark_content_drift(run_id: int, db_registry_id: Optional[int]) -> int:
    """
    Compare object content_hash in `run_id` against the most recent prior run
    for the same database.  Objects where the hash changed get content_drift=TRUE.

    Returns number of objects marked as drifted.
    """
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Find the previous run for the same DB
            if db_registry_id is not None:
                cur.execute("""
                    SELECT id FROM runs
                     WHERE db_registry_id = %s AND id < %s
                     ORDER BY id DESC LIMIT 1
                """, (db_registry_id, run_id))
            else:
                cur.execute("""
                    SELECT id FROM runs
                     WHERE db_registry_id IS NULL AND id < %s
                     ORDER BY id DESC LIMIT 1
                """, (run_id,))
            prev = cur.fetchone()
            if not prev:
                return 0
            prev_run_id = prev[0]

            # Mark objects whose hash changed
            cur.execute("""
                UPDATE object_snapshots curr
                   SET content_drift = TRUE
                  FROM object_snapshots prev
                 WHERE curr.run_id  = %s
                   AND prev.run_id  = %s
                   AND curr.object_name = prev.object_name
                   AND curr.content_hash IS NOT NULL
                   AND prev.content_hash IS NOT NULL
                   AND curr.content_hash != prev.content_hash
            """, (run_id, prev_run_id))
            return cur.rowcount or 0
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("detect_and_mark_content_drift failed: %s", exc)
        return 0


# ─── Findings Deduplication ──────────────────────────────────────────────────

def enrich_findings_with_history(run_id: int, db_registry_id: Optional[int]) -> int:
    """
    For each finding in `run_id`, look up whether the same (object_name, rule_id)
    pair appeared in any prior run for the same database.

    - If found in a prior run: set is_new=FALSE, first_seen_run=<original run_id>
    - If first occurrence: is_new=TRUE (already default), first_seen_run=run_id

    Also sets last_seen_run=run_id for all findings in this run.

    Returns number of findings updated as non-new (i.e. duplicates suppressed).
    """
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Set last_seen_run for all findings in this run
            cur.execute("""
                UPDATE findings SET last_seen_run = %s WHERE run_id = %s
            """, (run_id, run_id))

            # For findings that appear in a prior run, mark them as non-new
            # and set first_seen_run to the earliest prior occurrence
            if db_registry_id is not None:
                cur.execute("""
                    UPDATE findings f
                       SET is_new         = FALSE,
                           first_seen_run = (
                               SELECT MIN(prev.run_id)
                                 FROM findings prev
                                 JOIN runs r ON r.id = prev.run_id
                                WHERE r.db_registry_id = %s
                                  AND prev.run_id < f.run_id
                                  AND prev.object_name = f.object_name
                                  AND prev.rule_id     = f.rule_id
                           )
                     WHERE f.run_id = %s
                       AND f.rule_id IS NOT NULL
                       AND EXISTS (
                           SELECT 1 FROM findings prev
                             JOIN runs r ON r.id = prev.run_id
                            WHERE r.db_registry_id = %s
                              AND prev.run_id < f.run_id
                              AND prev.object_name = f.object_name
                              AND prev.rule_id     = f.rule_id
                       )
                """, (db_registry_id, run_id, db_registry_id))
            else:
                cur.execute("""
                    UPDATE findings f
                       SET is_new         = FALSE,
                           first_seen_run = (
                               SELECT MIN(prev.run_id)
                                 FROM findings prev
                                WHERE prev.run_id < f.run_id
                                  AND prev.object_name = f.object_name
                                  AND prev.rule_id     = f.rule_id
                           )
                     WHERE f.run_id = %s
                       AND f.rule_id IS NOT NULL
                       AND EXISTS (
                           SELECT 1 FROM findings prev
                            WHERE prev.run_id < f.run_id
                              AND prev.object_name = f.object_name
                              AND prev.rule_id     = f.rule_id
                       )
                """, (run_id,))
            return cur.rowcount or 0
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("enrich_findings_with_history failed: %s", exc)
        return 0


def get_db_summary() -> List[Dict[str, Any]]:
    """
    One row per registered database with its latest run stats.
    Used for the 'All Databases' dashboard overview page.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                d.id,
                d.name,
                d.environment,
                d.owner_label,
                d.last_run_at,
                d.last_health,
                d.is_active,
                d.tags,
                r.id             AS last_run_id,
                r.label          AS last_run_label,
                r.timestamp      AS last_run_ts,
                r.total_objects,
                r.total_issues,
                r.critical_count,
                r.high_count,
                r.medium_count,
                r.low_count,
                r.health_score,
                r.duration_sec,
                r.status         AS run_status
            FROM db_registry d
            LEFT JOIN LATERAL (
                SELECT * FROM runs
                 WHERE db_registry_id = d.id
                 ORDER BY timestamp DESC LIMIT 1
            ) r ON TRUE
            WHERE d.is_active = TRUE
            ORDER BY COALESCE(r.health_score, 0) ASC
        """)
        return [dict(r) for r in cur.fetchall()]


# ─── Scheduled Tasks ──────────────────────────────────────────────────────────

def list_schedules() -> List[Dict[str, Any]]:
    """Return all scheduled tasks ordered by db_name."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, db_name, schedule, label, enabled,
                   last_run, next_run, run_dmv, formats, created_at, updated_at
              FROM scheduled_tasks
             ORDER BY db_name
        """)
        return [dict(r) for r in cur.fetchall()]


def upsert_schedule(db_name: str, schedule: str, label: str,
                    enabled: bool, run_dmv: bool, formats: list) -> Dict[str, Any]:
    """Insert or update a scheduled task (keyed by db_name). Returns the row."""
    import json as _json
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM scheduled_tasks WHERE db_name = %s", (db_name,))
        existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE scheduled_tasks
                   SET schedule=%s, label=%s, enabled=%s, run_dmv=%s,
                       formats=%s, updated_at=NOW()
                 WHERE db_name=%s RETURNING id
            """, (schedule, label, enabled, run_dmv,
                  _json.dumps(formats), db_name))
        else:
            cur.execute("""
                INSERT INTO scheduled_tasks (db_name, schedule, label, enabled, run_dmv, formats)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """, (db_name, schedule, label, enabled, run_dmv, _json.dumps(formats)))
        row_id = cur.fetchone()[0]
    with get_cursor() as cur:
        cur.execute("SELECT * FROM scheduled_tasks WHERE id=%s", (row_id,))
        return dict(cur.fetchone())


def delete_schedule(schedule_id: int) -> bool:
    """Delete a scheduled task by ID. Returns True if found."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM scheduled_tasks WHERE id=%s", (schedule_id,))
        return cur.rowcount > 0


def toggle_schedule(schedule_id: int, enabled: bool) -> bool:
    """Enable or disable a scheduled task. Returns True if found."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE scheduled_tasks SET enabled=%s, updated_at=NOW()
             WHERE id=%s
        """, (enabled, schedule_id))
        return cur.rowcount > 0


def mark_schedule_ran(schedule_id: int) -> None:
    """Update last_run timestamp after a manual trigger."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE scheduled_tasks SET last_run=NOW(), updated_at=NOW()
             WHERE id=%s
        """, (schedule_id,))
