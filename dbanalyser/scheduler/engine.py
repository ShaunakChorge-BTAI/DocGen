"""
Scheduled Scan Engine
======================
Run DBAnalyser on a cron-like schedule.  Schedules are stored in PostgreSQL
so they survive restarts and are visible to all API / CLI clients.

Schedule formats
----------------
  hourly                  — top of every hour
  daily@HH:MM             — e.g. daily@02:00
  weekly@DAY@HH:MM        — e.g. weekly@mon@06:00
  manual                  — never runs automatically

CLI commands
------------
  dbanalyser schedule list
  dbanalyser schedule add  <DB_NAME> --cron "daily@02:00" [--label "nightly"]
  dbanalyser schedule remove <DB_NAME>
  dbanalyser schedule run-due [--config <path>]    ← call from Windows Task Scheduler
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

log = logging.getLogger(__name__)


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class ScheduledTask:
    db_name:  str
    schedule: str                          # "daily@02:00" | "weekly@mon@06:00" | "hourly" | "manual"
    label:    str                  = ""
    enabled:  bool                 = True
    last_run: Optional[datetime]   = None
    next_run: Optional[datetime]   = None
    run_dmv:  bool                 = False
    formats:  List[str]            = field(default_factory=lambda: ["json"])
    task_id:  Optional[int]        = None


# ─── Schedule parser ──────────────────────────────────────────────────────────

def parse_next_run(schedule: str, after: Optional[datetime] = None) -> datetime:
    """
    Compute the next UTC run time from a schedule string.

    Returns a far-future datetime for "manual" schedules.
    """
    now = after or datetime.now(timezone.utc)
    s   = schedule.strip().lower()

    if s == "hourly":
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    if s.startswith("daily@"):
        time_part = s.split("@", 1)[1]
        h, m = (int(x) for x in time_part.split(":"))
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if s.startswith("weekly@"):
        parts     = s.split("@")
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        day_name  = parts[1] if len(parts) > 1 else "mon"
        day_idx   = day_names.index(day_name) if day_name in day_names else 0
        time_str  = parts[2] if len(parts) > 2 else "06:00"
        h, m      = (int(x) for x in time_str.split(":"))
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        days_ahead = (day_idx - candidate.weekday()) % 7
        if days_ahead == 0 and candidate <= now:
            days_ahead = 7
        return candidate + timedelta(days=days_ahead)

    # manual / unknown — schedule far in the future
    return now.replace(year=now.year + 20)


# ─── Repository helpers ───────────────────────────────────────────────────────

def list_tasks() -> List[dict]:
    """Return all scheduled tasks from PostgreSQL."""
    try:
        from dbanalyser.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, db_name, schedule, label, enabled,
                       last_run, next_run, run_dmv, formats
                FROM   scheduled_tasks
                ORDER  BY next_run NULLS LAST
            """)
            return list(cur.fetchall() or [])
    except Exception as exc:
        log.warning("list_tasks — DB unavailable: %s", exc)
        return []


def add_task(task: ScheduledTask) -> int:
    """Insert or update a scheduled task.  Returns the task id (-1 on error)."""
    next_run = parse_next_run(task.schedule)
    try:
        from dbanalyser.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO scheduled_tasks
                    (db_name, schedule, label, enabled, next_run, run_dmv, formats)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (db_name) DO UPDATE SET
                    schedule   = EXCLUDED.schedule,
                    label      = EXCLUDED.label,
                    enabled    = EXCLUDED.enabled,
                    next_run   = EXCLUDED.next_run,
                    run_dmv    = EXCLUDED.run_dmv,
                    formats    = EXCLUDED.formats,
                    updated_at = NOW()
                RETURNING id
            """, (
                task.db_name, task.schedule, task.label, task.enabled,
                next_run, task.run_dmv, json.dumps(task.formats),
            ))
            row = cur.fetchone()
            return int(row["id"]) if row else -1
    except Exception as exc:
        log.error("add_task failed: %s", exc)
        return -1


def remove_task(db_name: str) -> bool:
    """Delete a scheduled task by db_name.  Returns True if a row was deleted."""
    try:
        from dbanalyser.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM scheduled_tasks WHERE db_name = %s RETURNING id",
                (db_name,),
            )
            return cur.fetchone() is not None
    except Exception as exc:
        log.error("remove_task failed: %s", exc)
        return False


# ─── Run-due executor ─────────────────────────────────────────────────────────

def run_due_tasks(config_path: str = "analysis_config.yaml") -> int:
    """
    Find and execute every task whose next_run <= NOW().

    Called by:  ``dbanalyser schedule run-due``
    Typical use: Windows Task Scheduler running every minute.

    Returns:
        Number of tasks successfully executed.
    """
    from dbanalyser.config import load_config
    from dbanalyser.engine import run_analysis

    cfg   = load_config(config_path)
    count = 0

    try:
        from dbanalyser.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, db_name, schedule, label, run_dmv, formats
                FROM   scheduled_tasks
                WHERE  enabled = TRUE
                  AND  (next_run IS NULL OR next_run <= NOW())
            """)
            due = list(cur.fetchall() or [])
    except Exception as exc:
        log.error("Cannot fetch due tasks from PostgreSQL: %s", exc)
        return 0

    for row in due:
        db_name  = row["db_name"]
        schedule = row.get("schedule", "manual")
        label    = row.get("label") or f"{db_name}_{time.strftime('%Y%m%d_%H%M%S')}"

        log.info("Running scheduled task for '%s' (schedule=%s, label=%s)",
                 db_name, schedule, label)
        try:
            db_entry = cfg.get_database(db_name)
            if not db_entry:
                log.warning(
                    "Scheduled task: database '%s' not found in config — skipping",
                    db_name,
                )
                continue

            db_cfg = cfg.settings_for_database(db_entry)
            run_analysis(db_cfg, run_label=label, db_name=db_name)
            count += 1

            # Update last_run + next_run in DB
            next_run = parse_next_run(schedule)
            try:
                from dbanalyser.db.connection import get_cursor as _gc
                with _gc() as cur2:
                    cur2.execute(
                        "UPDATE scheduled_tasks SET last_run=NOW(), next_run=%s WHERE id=%s",
                        (next_run, row["id"]),
                    )
            except Exception as exc2:
                log.warning("Could not update next_run for task id=%s: %s", row["id"], exc2)

        except Exception as exc:
            log.error("Scheduled task for '%s' failed: %s", db_name, exc)

    log.info("run_due_tasks complete: %d task(s) executed.", count)
    return count
