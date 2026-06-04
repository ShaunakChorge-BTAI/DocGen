-- Phase 5 Unified Assessment Wizard Schema Migration
-- Date: 2026-04-08

BEGIN;

-- ============================================================================
-- PHASE 5: Assessment Wizard & Templates
-- ============================================================================

CREATE TABLE assessment_templates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(255) NOT NULL,
    description TEXT,
    scope_rules JSONB,
    filters JSONB,
    is_public BOOLEAN DEFAULT false,
    created_by_user_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE assessment_sessions (
    id SERIAL PRIMARY KEY,
    session_token VARCHAR(255) UNIQUE,
    user_id INTEGER,
    current_step INTEGER,  -- 1-4
    selected_databases JSONB,
    assessment_config JSONB,
    scan_progress INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'in_progress',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE assessment_runs (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES assessment_sessions(id),
    run_date TIMESTAMP,
    databases_scanned INTEGER,
    objects_scanned INTEGER,
    findings_count INTEGER,
    critical_count INTEGER,
    execution_time_ms INTEGER,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE assessment_comparisons (
    id SERIAL PRIMARY KEY,
    database_id INTEGER REFERENCES db_registry(id),
    baseline_run_id INTEGER REFERENCES assessment_runs(id),
    current_run_id INTEGER REFERENCES assessment_runs(id),
    comparison_date TIMESTAMP,
    findings_improved INTEGER,
    findings_regressed INTEGER,
    findings_new INTEGER,
    critical_increase INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE assessment_recommendations (
    id SERIAL PRIMARY KEY,
    finding_id INTEGER REFERENCES findings(id),
    recommendation_type VARCHAR(50),
    recommendation_text TEXT,
    implementation_effort VARCHAR(20),
    estimated_benefit VARCHAR(20),
    priority_score INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- PHASE 5: Indexes for Performance
-- ============================================================================

DROP INDEX IF EXISTS idx_assessment_templates_public;
DROP INDEX IF EXISTS idx_assessment_sessions_user;
DROP INDEX IF EXISTS idx_assessment_sessions_token;
DROP INDEX IF EXISTS idx_assessment_runs_session;
DROP INDEX IF EXISTS idx_assessment_comparisons_db;
DROP INDEX IF EXISTS idx_assessment_recommendations_finding;

CREATE INDEX idx_assessment_templates_public ON assessment_templates(is_public, created_at DESC);
CREATE INDEX idx_assessment_sessions_user ON assessment_sessions(user_id, created_at DESC);
CREATE INDEX idx_assessment_sessions_token ON assessment_sessions(session_token);
CREATE INDEX idx_assessment_sessions_status ON assessment_sessions(status);
CREATE INDEX idx_assessment_runs_session ON assessment_runs(session_id);
CREATE INDEX idx_assessment_runs_date ON assessment_runs(run_date DESC);
CREATE INDEX idx_assessment_comparisons_db ON assessment_comparisons(database_id);
CREATE INDEX idx_assessment_comparisons_date ON assessment_comparisons(comparison_date DESC);
CREATE INDEX idx_assessment_recommendations_finding ON assessment_recommendations(finding_id);
CREATE INDEX idx_assessment_recommendations_priority ON assessment_recommendations(priority_score DESC);

COMMIT;
