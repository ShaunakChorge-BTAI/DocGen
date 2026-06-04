-- Phase 4 Database Management + CR Workflow Schema Migration
-- Date: 2026-04-08

BEGIN;

-- ============================================================================
-- PHASE 4: Database Version Management
-- ============================================================================

CREATE TABLE database_versions (
    id SERIAL PRIMARY KEY,
    db_registry_id INTEGER REFERENCES db_registry(id),
    version_number INTEGER,
    version_date TIMESTAMP,
    patch_notes TEXT,
    deployed_by_user_id INTEGER,
    deployed_at TIMESTAMP,
    is_rollback BOOLEAN DEFAULT false,
    rollback_target_version INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- PHASE 4: Change Request Workflow
-- ============================================================================

CREATE TABLE change_request_workflow (
    id SERIAL PRIMARY KEY,
    cr_id VARCHAR(100) UNIQUE NOT NULL,
    finding_id INTEGER REFERENCES findings(id),
    optimization_id INTEGER REFERENCES schema_object_optimizations(id),
    title TEXT NOT NULL,
    description TEXT,
    created_by_user_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'draft',
    priority VARCHAR(20),  -- low, medium, high, critical
    estimated_duration_mins INTEGER,
    actual_duration_mins INTEGER
);

CREATE TABLE cr_approvals (
    id SERIAL PRIMARY KEY,
    cr_id VARCHAR(100) REFERENCES change_request_workflow(cr_id),
    approval_stage INTEGER,
    approval_role VARCHAR(100),
    assigned_to_user_id INTEGER,
    approved_by_user_id INTEGER,
    approval_date TIMESTAMP,
    comment TEXT,
    status VARCHAR(20),  -- pending, approved, rejected
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE cr_deployments (
    id SERIAL PRIMARY KEY,
    cr_id VARCHAR(100) REFERENCES change_request_workflow(cr_id),
    deployment_env VARCHAR(50),  -- staging, production
    deployment_date TIMESTAMP,
    deployed_by_user_id INTEGER,
    deployment_duration_mins INTEGER,
    status VARCHAR(50),  -- in_progress, success, failed, rolled_back
    error_details TEXT,
    pre_deployment_check_passed BOOLEAN,
    post_deployment_validation_passed BOOLEAN,
    rollback_available_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE deployment_audit_log (
    id SERIAL PRIMARY KEY,
    cr_id VARCHAR(100),
    event_type VARCHAR(100),
    event_timestamp TIMESTAMP,
    user_id INTEGER,
    details TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pre_deployment_checks (
    id SERIAL PRIMARY KEY,
    cr_id VARCHAR(100) REFERENCES change_request_workflow(cr_id),
    check_type VARCHAR(100),  -- syntax, security, performance, compatibility
    check_result VARCHAR(50),  -- pass, fail, warning
    details TEXT,
    checked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE post_deployment_validation (
    id SERIAL PRIMARY KEY,
    cr_id VARCHAR(100) REFERENCES change_request_workflow(cr_id),
    test_name VARCHAR(255),
    test_result VARCHAR(50),  -- passed, failed, skipped
    error_details TEXT,
    validated_at TIMESTAMP,
    validated_by_user_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE deployment_rollback (
    id SERIAL PRIMARY KEY,
    cr_id VARCHAR(100),
    original_deployment_id INTEGER REFERENCES cr_deployments(id),
    rollback_date TIMESTAMP,
    rollback_reason TEXT,
    rolled_back_by_user_id INTEGER,
    rollback_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- PHASE 4: Indexes for Performance
-- ============================================================================

DROP INDEX IF EXISTS idx_database_versions_registry;
DROP INDEX IF EXISTS idx_change_request_status;
DROP INDEX IF EXISTS idx_cr_approvals_cr;
DROP INDEX IF EXISTS idx_cr_deployments_cr;
DROP INDEX IF EXISTS idx_deployment_audit_cr;

CREATE INDEX idx_database_versions_registry ON database_versions(db_registry_id, version_date DESC);
CREATE INDEX idx_change_request_status ON change_request_workflow(status, created_at DESC);
CREATE INDEX idx_change_request_finding ON change_request_workflow(finding_id);
CREATE INDEX idx_cr_approvals_cr ON cr_approvals(cr_id);
CREATE INDEX idx_cr_approvals_status ON cr_approvals(status, approval_stage);
CREATE INDEX idx_cr_deployments_cr ON cr_deployments(cr_id);
CREATE INDEX idx_cr_deployments_status ON cr_deployments(status);
CREATE INDEX idx_deployment_audit_cr ON deployment_audit_log(cr_id);
CREATE INDEX idx_pre_deployment_cr ON pre_deployment_checks(cr_id);
CREATE INDEX idx_post_deployment_cr ON post_deployment_validation(cr_id);

COMMIT;
