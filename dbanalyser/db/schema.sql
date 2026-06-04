-- =============================================================================
-- DBAnalyser  —  PostgreSQL Results Schema  (v2 — multi-DB + trend)
-- Run once:  psql -U postgres -d dbanalyser -f schema.sql
-- Or via:    dbanalyser init-db
-- Safe to re-run (all CREATE ... IF NOT EXISTS + ALTER ... IF NOT EXISTS)
-- =============================================================================

-- ── db_registry ───────────────────────────────────────────────────────────────
-- Central catalogue of every database being monitored (multi-DB support).
CREATE TABLE IF NOT EXISTS db_registry (
    id              SERIAL      PRIMARY KEY,
    name            TEXT        NOT NULL,   -- friendly label e.g. "LTFS_PROD"
    db_type         TEXT        NOT NULL DEFAULT 'mssql',
                    -- mssql | oracle | postgresql | mysql | snowflake | mariadb
    environment     TEXT        NOT NULL DEFAULT 'development',
                    -- development | uat | production | staging
    host            TEXT        NOT NULL DEFAULT 'localhost',
    port            INTEGER,                          -- NULL = use db_type default
    database_name   TEXT        NOT NULL DEFAULT '',
    connection_string TEXT,                         -- full DSN (overrides host/port/db)
    use_windows_auth BOOLEAN    NOT NULL DEFAULT FALSE,  -- MSSQL only
    username        TEXT,
    password        TEXT,                             -- SQL Auth password (stored in plaintext; use connection_string or vault for security)
    oracle_sid_or_service TEXT,                      -- Oracle SID or service name
    snowflake_warehouse TEXT,                        -- Snowflake warehouse
    snowflake_role  TEXT,                            -- Snowflake role
    encryption_key_id INTEGER,                       -- Future: for encrypted credentials
    description     TEXT,
    owner_label     TEXT,                           -- team / person responsible
    tags            TEXT[]      NOT NULL DEFAULT '{}',
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    last_health     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, name, db_type, host, port)
);
CREATE INDEX IF NOT EXISTS idx_registry_env    ON db_registry(environment);
CREATE INDEX IF NOT EXISTS idx_registry_active ON db_registry(is_active);
CREATE INDEX IF NOT EXISTS idx_registry_db_type ON db_registry(db_type);

-- ── runs ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS runs (
    id              BIGSERIAL   PRIMARY KEY,        -- integer PK for FK joins
    run_id          TEXT        NOT NULL UNIQUE,    -- UUID string label
    db_registry_id  INTEGER     REFERENCES db_registry(id) ON DELETE SET NULL,
    label           TEXT        NOT NULL DEFAULT '',
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    environment     TEXT        NOT NULL DEFAULT 'development',
    source_mode     TEXT        NOT NULL DEFAULT 'file',
    config_hash     TEXT,
    file_input_path TEXT,
    database_name   TEXT,
    host            TEXT,
    duration_sec    REAL,
    total_objects   INTEGER     NOT NULL DEFAULT 0,
    total_issues    INTEGER     NOT NULL DEFAULT 0,
    critical_count  INTEGER     NOT NULL DEFAULT 0,
    high_count      INTEGER     NOT NULL DEFAULT 0,
    medium_count    INTEGER     NOT NULL DEFAULT 0,
    low_count       INTEGER     NOT NULL DEFAULT 0,
    health_score    REAL,
    status          TEXT        NOT NULL DEFAULT 'success',
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_runs_registry   ON runs(db_registry_id);
CREATE INDEX IF NOT EXISTS idx_runs_timestamp  ON runs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_runs_run_id     ON runs(run_id);

-- ── object_snapshots ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS object_snapshots (
    id              BIGSERIAL   PRIMARY KEY,
    run_id          BIGINT      NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    object_name     TEXT        NOT NULL,
    object_type     TEXT        NOT NULL,
    schema_name     TEXT        NOT NULL DEFAULT 'dbo',
    file_path       TEXT,
    content_hash    TEXT,
    lines           INTEGER,
    size_kb         REAL,
    risk_score      REAL,
    risk_level      TEXT,
    issue_count     INTEGER     NOT NULL DEFAULT 0,
    critical_count  INTEGER     NOT NULL DEFAULT 0,
    high_count      INTEGER     NOT NULL DEFAULT 0,
    source          TEXT        NOT NULL DEFAULT 'file',
    snapshot_type   TEXT        NOT NULL DEFAULT 'file_scan',
                    -- file_scan | metadata_fetch | dmv_capture
    source_db_type  TEXT        DEFAULT 'mssql',
                    -- tracks which DB type produced this object (mssql | oracle | postgresql | mysql | snowflake)
    metadata_hash   TEXT,                            -- hash to detect schema changes between refreshes
    content_drift   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_snapshots_run    ON object_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_object ON object_snapshots(object_name);
CREATE INDEX IF NOT EXISTS idx_snapshots_type   ON object_snapshots(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_snapshots_db_type ON object_snapshots(source_db_type);

-- ── findings ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS findings (
    id              BIGSERIAL   PRIMARY KEY,
    run_id          BIGINT      NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    object_name     TEXT        NOT NULL,
    object_type     TEXT        NOT NULL DEFAULT '',
    schema_name     TEXT        NOT NULL DEFAULT 'dbo',
    category        TEXT        NOT NULL,
    issue           TEXT        NOT NULL,
    severity        TEXT        NOT NULL,
    line_number     INTEGER,
    recommendation  TEXT,
    snippet         TEXT,
    rule_id         TEXT,
    -- lifecycle
    status          TEXT        NOT NULL DEFAULT 'open',
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    fixed_at        TIMESTAMPTZ,
    suppressed_by   TEXT,
    suppressed_at   TIMESTAMPTZ,
    suppress_reason TEXT,
    suppress_expiry DATE,
    -- external refs
    jira_ticket     TEXT,
    notes           TEXT,
    -- first/last seen
    first_seen_run  BIGINT,
    last_seen_run   BIGINT,
    is_new          BOOLEAN     NOT NULL DEFAULT TRUE,
    is_regression   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_findings_run      ON findings(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_object   ON findings(object_name);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_status   ON findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_category ON findings(category);

-- ── dmv_snapshots ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dmv_snapshots (
    id              BIGSERIAL   PRIMARY KEY,
    run_id          BIGINT      NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    dmv_type        TEXT        NOT NULL,
                    -- dmv_index_usage | dmv_missing_indexes | dmv_slow_queries | dmv_blocking_chains | dmv_wait_statistics | dmv_table_sizes
    db_type         TEXT        NOT NULL DEFAULT 'mssql',
                    -- mssql | oracle | postgresql | mysql | snowflake
    source_system   TEXT        NOT NULL DEFAULT 'dmv',
                    -- dmv | performance_schema | account_usage | v$ (system catalog source)
    data_json       JSONB       NOT NULL,
    row_count       INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dmv_run  ON dmv_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_dmv_type ON dmv_snapshots(dmv_type);
CREATE INDEX IF NOT EXISTS idx_dmv_db_type ON dmv_snapshots(db_type);

-- ── health_trend (one row per run per db — fast time-series queries) ──────────
CREATE TABLE IF NOT EXISTS health_trend (
    id              BIGSERIAL   PRIMARY KEY,
    run_id          BIGINT      NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    db_registry_id  INTEGER     REFERENCES db_registry(id) ON DELETE CASCADE,
    db_name         TEXT        NOT NULL DEFAULT '',   -- denormalised for queries w/o join
    environment     TEXT        NOT NULL DEFAULT 'development',
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    health_score    REAL,
    total_objects   INTEGER     NOT NULL DEFAULT 0,
    total_issues    INTEGER     NOT NULL DEFAULT 0,
    critical_count  INTEGER     NOT NULL DEFAULT 0,
    high_count      INTEGER     NOT NULL DEFAULT 0,
    medium_count    INTEGER     NOT NULL DEFAULT 0,
    low_count       INTEGER     NOT NULL DEFAULT 0,
    new_issues      INTEGER     NOT NULL DEFAULT 0,
    resolved_issues INTEGER     NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_trend_registry  ON health_trend(db_registry_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trend_timestamp ON health_trend(timestamp DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uidx_trend_run ON health_trend(run_id);

-- ── scheduled_tasks (cron-like scan schedule) ────────────────────────────────
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id          SERIAL      PRIMARY KEY,
    db_name     TEXT        NOT NULL UNIQUE,
    schedule    TEXT        NOT NULL DEFAULT 'manual',
                -- hourly | daily@HH:MM | weekly@DAY@HH:MM | manual
    label       TEXT        NOT NULL DEFAULT '',
    enabled     BOOLEAN     NOT NULL DEFAULT TRUE,
    last_run    TIMESTAMPTZ,
    next_run    TIMESTAMPTZ,
    run_dmv     BOOLEAN     NOT NULL DEFAULT FALSE,
    formats     JSONB       NOT NULL DEFAULT '["json"]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sched_enabled  ON scheduled_tasks(enabled);
CREATE INDEX IF NOT EXISTS idx_sched_next_run ON scheduled_tasks(next_run);

-- ── jobs (persistent async job state — replaces in-process _JOBS dict) ────────
CREATE TABLE IF NOT EXISTS jobs (
    id          BIGSERIAL   PRIMARY KEY,
    job_id      TEXT        NOT NULL UNIQUE,
    status      TEXT        NOT NULL DEFAULT 'queued',
                -- queued | running | done | failed
    message     TEXT        NOT NULL DEFAULT '',
    run_id      BIGINT      REFERENCES runs(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- ── update trigger for findings.updated_at ───────────────────────────────────
CREATE OR REPLACE FUNCTION _set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_findings_updated ON findings;
CREATE TRIGGER trg_findings_updated
    BEFORE UPDATE ON findings
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

-- ── update trigger for db_registry.updated_at ────────────────────────────────
DROP TRIGGER IF EXISTS trg_registry_updated ON db_registry;
CREATE TRIGGER trg_registry_updated
    BEFORE UPDATE ON db_registry
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

DROP TRIGGER IF EXISTS trg_jobs_updated ON jobs;
CREATE TRIGGER trg_jobs_updated
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

DROP TRIGGER IF EXISTS trg_sched_updated ON scheduled_tasks;
CREATE TRIGGER trg_sched_updated
    BEFORE UPDATE ON scheduled_tasks
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

-- ── schema_objects (Schema Intelligence vector store) ─────────────────────────
CREATE TABLE IF NOT EXISTS schema_objects (
    id              BIGSERIAL   PRIMARY KEY,
    db_registry_id  INTEGER     REFERENCES db_registry(id) ON DELETE CASCADE,
    object_type     TEXT        NOT NULL,
                    -- table | view | procedure | function | column | index
    schema_name     TEXT        NOT NULL DEFAULT 'dbo',
    object_name     TEXT        NOT NULL,
    parent_name     TEXT        NOT NULL DEFAULT '',   -- for columns: parent table name
    data_type       TEXT,                              -- for columns
    is_nullable     BOOLEAN,
    is_primary_key  BOOLEAN     NOT NULL DEFAULT FALSE,
    is_foreign_key  BOOLEAN     NOT NULL DEFAULT FALSE,
    definition      TEXT,                              -- DDL snippet / column def
    embedding_json  TEXT,                              -- JSON array of floats
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (db_registry_id, object_type, schema_name, object_name, parent_name)
);
CREATE INDEX IF NOT EXISTS idx_schema_db       ON schema_objects(db_registry_id);
CREATE INDEX IF NOT EXISTS idx_schema_type     ON schema_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_schema_name     ON schema_objects(object_name);
CREATE INDEX IF NOT EXISTS idx_schema_parent   ON schema_objects(parent_name);

-- ── ai_optimizations (AI Optimizer audit trail) ───────────────────────────────
CREATE TABLE IF NOT EXISTS ai_optimizations (
    id                   BIGSERIAL   PRIMARY KEY,
    run_id               BIGINT      REFERENCES runs(id) ON DELETE SET NULL,
    db_registry_id       INTEGER     REFERENCES db_registry(id) ON DELETE SET NULL,
    object_name          TEXT        NOT NULL,
    original_sql         TEXT,
    optimized_sql        TEXT,
    reasoning            TEXT,
    schema_context_used  TEXT,
    execution_plan_used  TEXT,
    findings_used        JSONB       NOT NULL DEFAULT '[]',
    confidence_score     REAL        NOT NULL DEFAULT 0.0,
    model_used           TEXT        NOT NULL DEFAULT '',
    tokens_used          INTEGER     NOT NULL DEFAULT 0,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_aiopt_object     ON ai_optimizations(object_name);
CREATE INDEX IF NOT EXISTS idx_aiopt_run        ON ai_optimizations(run_id);
CREATE INDEX IF NOT EXISTS idx_aiopt_created    ON ai_optimizations(created_at DESC);

-- ── audit_logs (user action history) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id              BIGSERIAL   PRIMARY KEY,
    username        TEXT        NOT NULL DEFAULT 'system',
    action          TEXT        NOT NULL,
                    -- login | logout | run_scan | optimize | ingest | view | export | ...
    resource_type   TEXT        NOT NULL DEFAULT '',
                    -- stored_procedure | database | finding | report | ...
    resource_id     TEXT        NOT NULL DEFAULT '',
    details         JSONB       NOT NULL DEFAULT '{}',
    ip_address      TEXT        NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_username   ON audit_logs(username);
CREATE INDEX IF NOT EXISTS idx_audit_action     ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_created    ON audit_logs(created_at DESC);

-- ── pipeline_steps (per-run pipeline observability) ──────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_steps (
    id              BIGSERIAL   PRIMARY KEY,
    run_id          BIGINT      REFERENCES runs(id) ON DELETE CASCADE,
    step            TEXT        NOT NULL,
                    -- schema_ingest | embed | scan | rules | ai_optimize | report
    status          TEXT        NOT NULL DEFAULT 'pending',
                    -- pending | running | done | failed | skipped
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_sec    REAL,
    error           TEXT,
    details         JSONB       NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_pipeline_run     ON pipeline_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_step    ON pipeline_steps(step);
CREATE INDEX IF NOT EXISTS idx_pipeline_status  ON pipeline_steps(status);

-- ── metadata_refresh_log (track metadata refresh operations) ────────────────────
CREATE TABLE IF NOT EXISTS metadata_refresh_log (
    id              BIGSERIAL   PRIMARY KEY,
    run_id          BIGINT      REFERENCES runs(id) ON DELETE SET NULL,
    db_registry_id  INTEGER     NOT NULL REFERENCES db_registry(id) ON DELETE CASCADE,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT        NOT NULL DEFAULT 'success',
                    -- success | failed | partial
    objects_fetched INTEGER     NOT NULL DEFAULT 0,
    objects_changed INTEGER     NOT NULL DEFAULT 0,
    error_message   TEXT,
    execution_time_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_metadata_refresh_db ON metadata_refresh_log(db_registry_id);
CREATE INDEX IF NOT EXISTS idx_metadata_refresh_timestamp ON metadata_refresh_log(timestamp DESC);

-- =============================================================================
-- PHASE G — Multi-Tenancy Foundation
-- Safe to re-run (IF NOT EXISTS + IF EXISTS guards throughout)
-- =============================================================================

-- ── organizations ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    id          SERIAL      PRIMARY KEY,
    name        TEXT        NOT NULL,
    slug        TEXT        NOT NULL UNIQUE,   -- url-safe identifier e.g. "ltfs-prod"
    plan        TEXT        NOT NULL DEFAULT 'free',  -- free | pro | enterprise
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_orgs_slug     ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_orgs_active   ON organizations(is_active);

-- ── users (replaces analysis_config.yaml auth.users list) ────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL      PRIMARY KEY,
    org_id          INTEGER     NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    username        TEXT        NOT NULL,
    email           TEXT        NOT NULL,
    password_hash   TEXT        NOT NULL,
    role            TEXT        NOT NULL DEFAULT 'viewer',  -- viewer | analyst | admin
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, username),
    UNIQUE (org_id, email)
);
CREATE INDEX IF NOT EXISTS idx_users_org    ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_users_email  ON users(email);

-- ── assessment_configs (per-database rule/threshold overrides) ────────────────
CREATE TABLE IF NOT EXISTS assessment_configs (
    id              SERIAL      PRIMARY KEY,
    org_id          INTEGER     NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    db_registry_id  INTEGER     NOT NULL REFERENCES db_registry(id) ON DELETE CASCADE,
    config_json     JSONB       NOT NULL DEFAULT '{}',
                    -- keys: enabled_rules[], disabled_rules[], compliance_packs[],
                    --        max_procedure_lines, nesting_depth, severity_threshold
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, db_registry_id)
);
CREATE INDEX IF NOT EXISTS idx_asmcfg_org ON assessment_configs(org_id);
CREATE INDEX IF NOT EXISTS idx_asmcfg_db  ON assessment_configs(db_registry_id);

-- ── invitations (pending user invites) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS invitations (
    id          SERIAL      PRIMARY KEY,
    org_id      INTEGER     NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email       TEXT        NOT NULL,
    role        TEXT        NOT NULL DEFAULT 'viewer',
    token       TEXT        NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token);
CREATE INDEX IF NOT EXISTS idx_invitations_org   ON invitations(org_id);

-- ── org_id columns on existing tables (safe: IF NOT EXISTS) ──────────────────
ALTER TABLE db_registry     ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE runs            ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL;
ALTER TABLE health_trend    ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL;
ALTER TABLE audit_logs      ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL;
ALTER TABLE audit_logs      ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS db_registry_id INTEGER REFERENCES db_registry(id) ON DELETE CASCADE;
ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS notify_email TEXT;
ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS report_formats JSONB DEFAULT '["excel","pdf"]';

-- ── db_registry: allow same name across different orgs ───────────────────────
ALTER TABLE db_registry DROP CONSTRAINT IF EXISTS db_registry_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS uidx_registry_org_name ON db_registry(org_id, name)
    WHERE org_id IS NOT NULL;

-- ── Indexes for new org_id columns ───────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_registry_org  ON db_registry(org_id);
CREATE INDEX IF NOT EXISTS idx_runs_org      ON runs(org_id);
CREATE INDEX IF NOT EXISTS idx_trend_org     ON health_trend(org_id);
CREATE INDEX IF NOT EXISTS idx_audit_org     ON audit_logs(org_id);
CREATE INDEX IF NOT EXISTS idx_sched_org     ON scheduled_tasks(org_id);

-- ── update triggers for new tables ───────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_orgs_updated ON organizations;
CREATE TRIGGER trg_orgs_updated
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

DROP TRIGGER IF EXISTS trg_users_updated ON users;
CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

DROP TRIGGER IF EXISTS trg_asmcfg_updated ON assessment_configs;
CREATE TRIGGER trg_asmcfg_updated
    BEFORE UPDATE ON assessment_configs
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();
