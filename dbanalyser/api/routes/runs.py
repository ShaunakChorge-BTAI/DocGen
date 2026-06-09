"""REST routes — /runs  (list, trigger, status)."""

from __future__ import annotations

import logging
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from dbanalyser.api.auth    import AuthDep
from dbanalyser.api.schemas import (
    HealthGateResponse, JobStatusResponse, PackGateResult,
    RunListResponse, RunResponse, RunTriggerRequest,
)
from dbanalyser.db.repository import get_run, list_runs

router = APIRouter(prefix="/runs", tags=["Runs"])
logger = logging.getLogger(__name__)

# ── In-process job registry (lightweight; replace with Redis/Celery for prod) ─
_JOBS: dict[str, dict] = {}

def update_job_progress(job_id: str, objects_analyzed: int, total_objects: int, current_phase: str = ""):
    """Update job progress with detailed metrics."""
    if job_id in _JOBS:
        progress = 0
        if total_objects > 0:
            progress = int((objects_analyzed / total_objects) * 100)
        phase_str = f" — {current_phase}" if current_phase else ""
        _JOBS[job_id].update({
            "objects_analyzed": objects_analyzed,
            "total_objects": total_objects,
            "progress_percent": progress,
            "message": f"Analysing [{objects_analyzed}/{total_objects}] {progress}%{phase_str}",
        })


@router.get("", response_model=RunListResponse, dependencies=[AuthDep])
def list_all_runs(
    db_name: Optional[str] = Query(None, description="Filter by database name"),
    limit:   int           = Query(50, ge=1, le=500),
):
    """List analysis runs, newest first."""
    from dbanalyser.db.repository import get_db_registry
    db_id = None
    if db_name:
        row = get_db_registry(db_name)
        if not row:
            raise HTTPException(404, f"Database '{db_name}' not registered.")
        db_id = row["id"]

    rows = list_runs(limit=limit, db_registry_id=db_id)
    return RunListResponse(
        runs=[RunResponse(
            id             = r["id"],
            run_id         = r["run_id"],
            label          = r.get("label", ""),
            db_name        = r.get("db_name"),
            environment    = r.get("environment"),
            source_mode    = r.get("source_mode", ""),
            health_score   = r.get("health_score"),
            total_objects  = r.get("total_objects", 0),
            total_issues   = r.get("total_issues", 0),
            critical_count = r.get("critical_count", 0),
            high_count     = r.get("high_count", 0),
            medium_count   = r.get("medium_count", 0),
            low_count      = r.get("low_count", 0),
            status         = r.get("status", ""),
            timestamp      = r.get("timestamp"),
            duration_sec   = r.get("duration_sec"),
        ) for r in rows],
        total=len(rows),
    )


@router.get("/{run_id}", response_model=RunResponse, dependencies=[AuthDep])
def get_single_run(run_id: int):
    """Get a single run by its integer ID."""
    row = get_run(run_id=run_id)
    if not row:
        raise HTTPException(404, f"Run {run_id} not found.")
    return RunResponse(
        id             = row["id"],
        run_id         = row["run_id"],
        label          = row.get("label", ""),
        db_name        = row.get("db_name"),
        environment    = row.get("environment"),
        source_mode    = row.get("source_mode", ""),
        health_score   = row.get("health_score"),
        total_objects  = row.get("total_objects", 0),
        total_issues   = row.get("total_issues", 0),
        critical_count = row.get("critical_count", 0),
        high_count     = row.get("high_count", 0),
        medium_count   = row.get("medium_count", 0),
        low_count      = row.get("low_count", 0),
        status         = row.get("status", ""),
        timestamp      = row.get("timestamp"),
        duration_sec   = row.get("duration_sec"),
    )


@router.get("/{run_id}/health-gate", response_model=HealthGateResponse, dependencies=[AuthDep])
def health_gate(
    run_id:       int,
    max_critical: int = Query(-1,  description="Max Critical findings (-1 = no limit)"),
    max_high:     int = Query(-1,  description="Max High findings (-1 = no limit)"),
    max_sox:      int = Query(-1,  description="Max Compliance-SOX findings (-1 = no limit)"),
    max_gdpr:     int = Query(-1,  description="Max Compliance-GDPR findings (-1 = no limit)"),
    max_rbi:      int = Query(-1,  description="Max Compliance-RBI findings (-1 = no limit)"),
    max_dng:      int = Query(-1,  description="Max Dangerous SQL findings (-1 = no limit)"),
):
    """
    CI/CD quality gate — returns 200 pass / 200 fail (check ``passed`` field).

    Example::

        GET /runs/42/health-gate?max_critical=0&max_sox=0&max_gdpr=2
    """
    row = get_run(run_id=run_id)
    if not row:
        raise HTTPException(404, f"Run {run_id} not found.")

    # ── Load findings for this run and count by category prefix ──────────────
    try:
        from dbanalyser.db.repository import get_findings
        findings_df = get_findings(run_id)
        import pandas as _pd
        if isinstance(findings_df, list):
            findings_df = _pd.DataFrame(findings_df)
    except Exception:
        findings_df = None

    def _count_category(prefix: str) -> int:
        if findings_df is None or findings_df.empty:
            return 0
        if "category" not in findings_df.columns:
            return 0
        return int(findings_df["category"].str.startswith(prefix, na=False).sum())

    def _count_severity(sev: str) -> int:
        if findings_df is None or findings_df.empty:
            return 0
        if "severity" not in findings_df.columns:
            return 0
        return int((findings_df["severity"] == sev).sum())

    checks: List[PackGateResult] = []

    def _add_check(name: str, count: int, threshold: int) -> None:
        if threshold >= 0:
            checks.append(PackGateResult(
                pack=name, count=count, threshold=threshold,
                passed=(count <= threshold),
            ))

    _add_check("critical",      _count_severity("Critical"),          max_critical)
    _add_check("high",          _count_severity("High"),               max_high)
    _add_check("Compliance-SOX", _count_category("Compliance-SOX"),   max_sox)
    _add_check("Compliance-GDPR", _count_category("Compliance-GDPR"), max_gdpr)
    _add_check("Compliance-RBI",  _count_category("Compliance-RBI"),  max_rbi)
    _add_check("Dangerous SQL",   _count_category("Dangerous SQL"),   max_dng)

    passed  = all(c.passed for c in checks)
    message = ("All quality gate checks passed." if passed
                else "Quality gate FAILED — "
                     + ", ".join(f"{c.pack}={c.count}>{c.threshold}"
                                 for c in checks if not c.passed))

    return HealthGateResponse(
        run_id       = run_id,
        passed       = passed,
        health_score = row.get("health_score"),
        checks       = checks,
        message      = message,
    )


@router.post("/trigger", response_model=JobStatusResponse, dependencies=[AuthDep])
def trigger_analysis(req: RunTriggerRequest, background_tasks: BackgroundTasks):
    """
    Trigger an analysis run asynchronously.
    Returns a job_id immediately; poll GET /runs/jobs/{job_id} for status.
    """
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        "status": "queued",
        "message": "Job queued",
        "run_id": None,
        "progress_percent": 0,
        "objects_analyzed": 0,
        "total_objects": None,
    }
    background_tasks.add_task(_run_job, job_id, req)
    return JobStatusResponse(job_id=job_id, status="queued",
                             message="Analysis job queued.",
                             progress_percent=0)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse, dependencies=[AuthDep])
def get_job_status(job_id: str):
    """Poll the status of a triggered analysis job."""
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")
    return JobStatusResponse(
        job_id  = job_id,
        status  = job["status"],
        message = job.get("message", ""),
        run_id  = job.get("run_id"),
        progress_percent = job.get("progress_percent", 0),
        objects_analyzed = job.get("objects_analyzed"),
        total_objects = job.get("total_objects"),
    )


# ── Background worker ─────────────────────────────────────────────────────────

def _run_job(job_id: str, req: RunTriggerRequest) -> None:
    """Runs in a background thread — performs the full analysis pipeline."""
    logger.info("=== JOB START %s ===", job_id)
    logger.info("req.db_name=%s", req.db_name)

    _JOBS[job_id]["status"] = "running"
    try:
        # Import here to avoid circular imports at module load time
        from dbanalyser.api.main    import _get_cfg
        from dbanalyser.engine      import run_analysis
        from dbanalyser.reports     import generate_json
        from dbanalyser.db.connection import init_pool, close_pool
        from dbanalyser.db.repository import get_db_registry

        cfg = _get_cfg()
        label = req.label or time.strftime("%Y%m%d_%H%M%S")

        logger.info("Config loaded, about to init_pool")

        # CRITICAL: Initialize PostgreSQL pool for database registry lookups
        init_pool(cfg.postgres)

        logger.info("init_pool completed successfully")

        db_entries = []
        db_registry_dict = {}  # map db_name to registry entry

        print(f"DEBUG: [_run_job] req.all_dbs={req.all_dbs}, req.db_name={req.db_name}")  # DEBUG
        if req.all_dbs:
            db_entries = cfg.get_active_databases()
            print(f"DEBUG: [_run_job] Using all_dbs, got {len(db_entries)} entries")  # DEBUG
        elif req.db_name:
            print(f"DEBUG: [_run_job] Using req.db_name={req.db_name}")  # DEBUG
            log = logging.getLogger(__name__)
            log.info(f"[_run_job] req.db_name={req.db_name}")

            # First try to get from YAML config
            entry = cfg.get_database(req.db_name)
            log.info(f"[_run_job] cfg.get_database result: {entry}")
            if entry:
                if not getattr(entry, 'is_active', True):
                    log.error(f"[_run_job] Scan Rejected: Database {req.db_name} is inactive. Aborting scan.")
                    _JOBS[job_id].update({"status": "failed", "message": f"Database '{req.db_name}' is inactive. Scan aborted."})
                    return
                db_entries = [entry]
            else:
                # Fall back to PostgreSQL registry
                log.info(f"[_run_job] Falling back to PostgreSQL registry for {req.db_name}")
                try:
                    reg_row = get_db_registry(req.db_name)
                    log.info(f"[_run_job] get_db_registry result: {reg_row is not None}")
                    if reg_row:
                        if not reg_row.get("is_active", True):
                            log.error(f"[_run_job] Scan Rejected: Database {req.db_name} is inactive. Aborting scan.")
                            _JOBS[job_id].update({"status": "failed", "message": f"Database '{req.db_name}' is inactive. Scan aborted."})
                            return
                        log.info(f"[_run_job] Creating DbEntry from registry row")
                        db_registry_dict[req.db_name] = reg_row
                        # Create a minimal entry object for compatibility
                        # class DbEntry:
                        #     def __init__(self, row):
                        #         self.name = row.get("name")
                        #         self.environment = row.get("environment")
                        #         self.host = row.get("host")
                        #         self.port = row.get("port")
                        #         self.database_name = row.get("database_name")
                        #         self.connection_string = row.get("connection_string")
                        #         self.use_windows_auth = row.get("use_windows_auth")
                        #         self.username = row.get("username")
                        #         self.password = row.get("password", "")  # CRITICAL: password for ODBC connection
                        #         self.description = row.get("description")
                        #         self.owner_label = row.get("owner_label")
                        #         self.tags = row.get("tags", [])
                        #         self.is_active = row.get("is_active")
                        #         self.id = row.get("id")

                        #     @property
                        #     def effective_connection_string(self) -> str:
                        #         """Return a ready-to-use pyodbc connection string."""
                        #         if self.connection_string:
                        #             return self.connection_string
                        #         import pyodbc
                        #         _drivers = pyodbc.drivers()
                        #         if "ODBC Driver 18 for SQL Server" in _drivers:
                        #             driver = "{ODBC Driver 18 for SQL Server}"
                        #         elif "ODBC Driver 17 for SQL Server" in _drivers:
                        #             driver = "{ODBC Driver 17 for SQL Server}"
                        #         else:
                        #             driver = "{SQL Server}"
                        #         base = f"DRIVER={driver};SERVER={self.host},{self.port};DATABASE={self.database_name};"
                        #         if self.use_windows_auth:
                        #             return base + "Trusted_Connection=yes;"
                        #         return base + f"UID={self.username};PWD={self.password};TrustServerCertificate=yes;"
                        # db_entries = [DbEntry(reg_row)]
                        # log.info(f"[_run_job] DbEntry created, db_entries now has {len(db_entries)} entries")

                        from dbanalyser.config import DatabaseEntry

                        db_obj = DatabaseEntry(
                            name=reg_row.get("name") or "temp",
                            db_type=reg_row.get("db_type") or "mssql",
                            environment=reg_row.get("environment") or "development",
                            host=reg_row.get("host") or "localhost",
                            port=reg_row.get("port"), # Port can stay as is (it accepts None)
                            database_name=reg_row.get("database_name") or "",
                            connection_string=reg_row.get("connection_string") or "",
                            use_windows_auth=bool(reg_row.get("use_windows_auth")),
                            username=reg_row.get("username") or "",
                            password=reg_row.get("password") or ""
                        )
                        db_entries = [db_obj]


                    else:
                        log.warning(f"[_run_job] No registry row found for {req.db_name}")
                except Exception as e:
                    import traceback
                    log.error(f"ERROR getting db_registry for {req.db_name}: {e}")
                    log.error(traceback.format_exc())
                    pass

        run_int_id = None
        run_int_ids = []

        logger.info("JOB %s: About to check db_entries, len=%s, req.db_name=%s", job_id, len(db_entries), req.db_name)
        for i, db in enumerate(db_entries):
            logger.info("  [%s] name=%s", i, getattr(db, 'name', 'NO NAME ATTR'))

        if db_entries:
            logger.info("JOB %s: Processing %s database entries in LIVE DB MODE", job_id, len(db_entries))
            for idx, db in enumerate(db_entries):
                logger.info("JOB %s: Entering for loop iteration %s/%s", job_id, idx + 1, len(db_entries))
                # Prevent running assessments on inactive databases
                if not getattr(db, 'is_active', True):
                    logger.error("JOB %s: Database %s is inactive. Skipping scan.", job_id, db.name)
                    continue
                try:
                    logger.info("JOB %s: Processing db=%s, host=%s, port=%s, user=%s", job_id, db.name, db.host, db.port, db.username)
                    db_cfg = cfg.settings_for_database(db)
                    logger.info(
                        "JOB %s: settings_for_database returned, mode=%s, connstr_len=%s",
                        job_id, db_cfg.source.mode, len(db_cfg.source.connection_string or ""),
                    )
                    logger.info("JOB %s: connection_string=%s", job_id, db_cfg.source.connection_string[:200])
                    result = run_analysis(db_cfg, run_label=f"{db.name}_{label}",
                                          db_name=db.name)
                except Exception as e:
                    logger.error("JOB %s: ERROR during processing: %s", job_id, str(e))
                    raise
                if not req.no_persist:
                    rid = _persist_result(cfg, result, f"{db.name}_{label}", db)
                    run_int_ids.append(rid)
                    run_int_id = rid  # last (or only) run id returned to caller
        else:
            logger.info("JOB %s: db_entries is empty, running in FILE MODE", job_id)
            result = run_analysis(cfg, run_label=label)
            if not req.no_persist:
                run_int_id = _persist_result(cfg, result, label, None)

        _JOBS[job_id].update({"status": "done", "message": "Analysis complete.", "run_id": run_int_id})

    except Exception as exc:
        error_msg = str(exc)
        logger.error("_run_job EXCEPTION: %s", type(exc).__name__)
        logger.error("  Message: %s", error_msg[:300])
        _JOBS[job_id].update({"status": "failed", "message": error_msg})


def _persist_result(cfg, result, run_label: str, db_entry) -> int:
    """Persist a result to PostgreSQL; returns run integer id."""
    from dbanalyser.db.connection import init_pool, close_pool
    from dbanalyser.db.repository import (
        insert_run, bulk_insert_findings, upsert_db_registry,
        update_db_registry_last_run, upsert_health_trend,
        detect_and_mark_content_drift, enrich_findings_with_history,
        bulk_insert_snapshots,
    )
    from dbanalyser.db.models import DbRegistry, Finding, HealthTrend, Run, ObjectSnapshot
    import uuid as _uuid
    import hashlib

    init_pool(cfg.postgres)
    logger.info("_persist_result called for db_entry=%s", db_entry.name if db_entry else None)
    try:
        db_registry_id = None
        if db_entry:
            reg = DbRegistry(
                name=db_entry.name,
                db_type=getattr(db_entry, 'db_type', 'mssql'),  # default to mssql if not specified
                environment=db_entry.environment,
                host=db_entry.host, port=db_entry.port,
                database_name=db_entry.database_name,
                connection_string=db_entry.connection_string or None,
                use_windows_auth=db_entry.use_windows_auth,
                username=db_entry.username or None,
                password=db_entry.password or None,
                description=db_entry.description or None,
                owner_label=db_entry.owner_label or None,
                tags=list(db_entry.tags), is_active=db_entry.is_active,
            )
            logger.info("About to upsert DbRegistry for %s", reg.name)
            logger.debug("  username=%s, password=%s", reg.username, reg.password)
            db_registry_id = upsert_db_registry(reg)
            logger.info("upsert_db_registry completed, id=%s", db_registry_id)

        sev = result.severity_counts
        run = Run(
            run_id=str(_uuid.uuid4()), label=run_label,
            db_registry_id=db_registry_id, source_mode=result.source_mode,
            total_objects=result.total_objects, total_issues=result.total_findings,
            critical_count=sev.get("Critical", 0), high_count=sev.get("High", 0),
            medium_count=sev.get("Medium", 0), low_count=sev.get("Low", 0),
            health_score=result.overall_health, status="success",
        )
        run_int_id = insert_run(run)

        snapshots = [
            ObjectSnapshot(
                run_id=run_int_id,
                object_name=or_.obj.name,
                object_type=or_.obj.obj_type,
                schema_name=or_.obj.schema or "dbo",
                file_path=or_.obj.file_path,
                content_hash=hashlib.md5(or_.obj.source.encode("utf-8")).hexdigest() if or_.obj.source else None,
                lines=or_.obj.lines,
                size_kb=or_.obj.size_kb,
                risk_score=or_.health_score,
                risk_level="CRITICAL" if or_.severity_counts.get("Critical", 0) > 0 else "HIGH" if or_.severity_counts.get("High", 0) > 0 else "MEDIUM" if or_.severity_counts.get("Medium", 0) > 0 else "MINIMAL",
                issue_count=len(or_.findings),
                critical_count=or_.severity_counts.get("Critical", 0),
                high_count=or_.severity_counts.get("High", 0),
                source="live_db" if result.source_mode == "live_db" else "file",
                content_drift=False,
            )
            for or_ in result.object_results
        ]
        logger.info("Created %s ObjectSnapshot objects", len(snapshots))
        bulk_insert_snapshots(snapshots)
        logger.info("bulk_insert_snapshots completed successfully")

        findings = [
            Finding(run_id=run_int_id, schema_name=or_.obj.schema,
                    object_name=or_.obj.name, object_type=or_.obj.obj_type,
                    rule_id=f.rule_id or "", category=f.category,
                    severity=f.severity, issue=f.issue,
                    recommendation=f.recommendation, line_number=f.line_number,
                    snippet=f.snippet or "")
            for or_ in result.object_results for f in or_.findings
        ]
        logger.info("Created %s Finding objects", len(findings))
        bulk_insert_findings(run_int_id, findings)
        logger.info("bulk_insert_findings completed successfully")

        # Drift detection + findings deduplication
        try:
            detect_and_mark_content_drift(run_int_id, db_registry_id)
            enrich_findings_with_history(run_int_id, db_registry_id)
        except Exception:
            pass  # non-critical; don't fail the run

        upsert_health_trend(HealthTrend(
            run_id=run_int_id, db_registry_id=db_registry_id,
            db_name=db_entry.name if db_entry else "",
            environment=cfg.run.environment,
            health_score=result.overall_health,
            total_objects=result.total_objects, total_issues=result.total_findings,
            critical_count=sev.get("Critical", 0), high_count=sev.get("High", 0),
            medium_count=sev.get("Medium", 0), low_count=sev.get("Low", 0),
        ))
        if db_registry_id:
            update_db_registry_last_run(db_registry_id, result.overall_health)
        return run_int_id
    finally:
        close_pool()
