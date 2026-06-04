-- ============================================================================
-- PHASE 1 MIGRATION: Metadata Storage + Status Tracking
-- Date: 2026-04-08
-- Description:
--   1. Migrate schema_objects to use TEXT (no truncation)
--   2. Add version history table
--   3. Add status tracking columns
--   4. Add comments table
--   5. Add search indexes
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Backup existing schema_objects
-- ============================================================================

CREATE TABLE schema_objects_backup AS
SELECT * FROM schema_objects;

-- ============================================================================
-- STEP 2: Add new columns to findings table (status tracking)
-- ============================================================================

ALTER TABLE findings ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'Pending';
ALTER TABLE findings ADD COLUMN IF NOT EXISTS assigned_to_user_id INT;
ALTER TABLE findings ADD COLUMN IF NOT EXISTS assigned_date TIMESTAMP;
ALTER TABLE findings ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMP DEFAULT NOW();
ALTER TABLE findings ADD COLUMN IF NOT EXISTS status_updated_by_user_id INT;
ALTER TABLE findings ADD COLUMN IF NOT EXISTS status_notes TEXT;
ALTER TABLE findings ADD COLUMN IF NOT EXISTS cr_link VARCHAR(500);
ALTER TABLE findings ADD COLUMN IF NOT EXISTS cr_link_type VARCHAR(50);
ALTER TABLE findings ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'Normal';
ALTER TABLE findings ADD COLUMN IF NOT EXISTS due_date TIMESTAMP;

-- Update any NULL or invalid status values to 'Pending'
UPDATE findings SET status = 'Pending' WHERE status IS NULL OR status NOT IN (
    'Pending', 'In Progress', 'Optimized', 'Reviewed',
    'CR_Submitted', 'CR_Approved', 'Ready_to_Deploy', 'Acknowledged'
);

-- Add check constraint for valid statuses (drop if exists first)
ALTER TABLE findings DROP CONSTRAINT IF EXISTS check_finding_status;
ALTER TABLE findings
ADD CONSTRAINT check_finding_status CHECK (
    status IN (
        'Pending',
        'In Progress',
        'Optimized',
        'Reviewed',
        'CR_Submitted',
        'CR_Approved',
        'Ready_to_Deploy',
        'Acknowledged'
    )
);

-- ============================================================================
-- STEP 3: Recreate schema_objects with TEXT (full definition)
-- ============================================================================

-- Create new table with improved schema
CREATE TABLE schema_objects_new (
    id SERIAL PRIMARY KEY,
    org_id INT NOT NULL REFERENCES organizations(id),
    db_registry_id INT NOT NULL REFERENCES db_registry(id),

    object_name VARCHAR(255) NOT NULL,
    object_type VARCHAR(50) NOT NULL,
    schema_name VARCHAR(255) DEFAULT 'dbo',

    -- FULL DEFINITION (no truncation)
    current_definition TEXT NOT NULL,
    definition_hash VARCHAR(64),
    definition_size_bytes INT,

    -- METADATA
    created_by_db TIMESTAMP,
    modified_by_db TIMESTAMP,

    -- SOURCING
    source_type VARCHAR(50) DEFAULT 'file_scan',
    source_path VARCHAR(500),

    -- TRACKING
    first_seen_run_id INT REFERENCES runs(id),
    last_seen_run_id INT REFERENCES runs(id),

    -- OPTIMIZATION
    optimized_version_id INT,
    optimization_status VARCHAR(50) DEFAULT 'none',

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(org_id, db_registry_id, schema_name, object_name)
);

-- Migrate data from old table to new table (only rows with definitions)
INSERT INTO schema_objects_new (
    org_id, db_registry_id, object_name, object_type, schema_name,
    current_definition, created_by_db, modified_by_db,
    source_type, source_path,
    first_seen_run_id, last_seen_run_id,
    created_at, updated_at
)
SELECT
    1 as org_id,
    db_registry_id,
    object_name,
    object_type,
    COALESCE(schema_name, 'dbo'),
    COALESCE(definition, '-- Definition not available'),
    ingested_at,
    ingested_at,
    'file_scan',
    NULL,
    NULL,
    NULL,
    COALESCE(ingested_at, NOW()),
    COALESCE(ingested_at, NOW())
FROM schema_objects
WHERE definition IS NOT NULL AND length(TRIM(definition)) > 0;

-- Drop old table and rename
DROP TABLE schema_objects CASCADE;
ALTER TABLE schema_objects_new RENAME TO schema_objects;

-- ============================================================================
-- STEP 4: Create version history table
-- ============================================================================

CREATE TABLE schema_object_versions (
    id SERIAL PRIMARY KEY,
    object_id INT NOT NULL REFERENCES schema_objects(id) ON DELETE CASCADE,

    version_number INT NOT NULL,
    definition TEXT NOT NULL,
    definition_hash VARCHAR(64),
    definition_size_bytes INT,

    -- CHANGE INFO
    change_type VARCHAR(50),
    change_reason TEXT,
    change_notes TEXT,

    -- WHO & WHEN
    changed_by_user_id INT REFERENCES users(id),
    changed_by_system VARCHAR(100),
    changed_at TIMESTAMP DEFAULT NOW(),

    -- OPTIMIZATION TRACKING
    is_optimized BOOLEAN DEFAULT FALSE,
    optimization_confidence INT,
    optimization_impact_pct INT,
    optimization_risk_level VARCHAR(20),

    -- DEPLOYMENT
    deployed_to_prod BOOLEAN DEFAULT FALSE,
    deployed_at TIMESTAMP,
    deployed_by_cr_id VARCHAR(100),

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(object_id, version_number),
    CONSTRAINT valid_version CHECK (version_number > 0)
);

-- Populate initial version records (v1 = current definition)
INSERT INTO schema_object_versions (
    object_id, version_number, definition, definition_hash,
    definition_size_bytes, change_type, changed_by_system,
    changed_at, is_optimized
)
SELECT
    id, 1, current_definition, definition_hash,
    definition_size_bytes, 'create', 'Migration from schema_objects_old',
    created_at, FALSE
FROM schema_objects;

-- ============================================================================
-- STEP 5: Create finding status history table
-- ============================================================================

CREATE TABLE finding_status_history (
    id SERIAL PRIMARY KEY,
    finding_id INT NOT NULL REFERENCES findings(id) ON DELETE CASCADE,

    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    changed_by_user_id INT REFERENCES users(id),
    changed_by_system VARCHAR(100),
    changed_at TIMESTAMP DEFAULT NOW(),
    reason TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- STEP 6: Create comments table
-- ============================================================================

CREATE TABLE finding_comments (
    id SERIAL PRIMARY KEY,
    finding_id INT NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id),

    comment_text TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by_user_id INT REFERENCES users(id)
);

-- ============================================================================
-- STEP 7: Create metadata sync history table
-- ============================================================================

CREATE TABLE metadata_sync_jobs (
    id SERIAL PRIMARY KEY,
    org_id INT NOT NULL REFERENCES organizations(id),
    db_registry_id INT NOT NULL REFERENCES db_registry(id),

    sync_type VARCHAR(50),
    source_type VARCHAR(50),
    objects_found INT,
    objects_created INT,
    objects_modified INT,
    objects_deleted INT,
    errors_count INT,

    status VARCHAR(50),
    error_message TEXT,

    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds INT,

    initiated_by_user_id INT REFERENCES users(id),
    initiated_by_system VARCHAR(100),

    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- STEP 8: Create indexes for performance (drop if exist first)
-- ============================================================================

-- findings indexes
DROP INDEX IF EXISTS idx_findings_run_id;
DROP INDEX IF EXISTS idx_findings_rule_id;
DROP INDEX IF EXISTS idx_findings_status;
DROP INDEX IF EXISTS idx_findings_severity;
DROP INDEX IF EXISTS idx_findings_assigned_to;
DROP INDEX IF EXISTS idx_findings_run_severity;
DROP INDEX IF EXISTS idx_findings_rule_status;

CREATE INDEX idx_findings_run_id ON findings(run_id);
CREATE INDEX idx_findings_rule_id ON findings(rule_id);
CREATE INDEX idx_findings_status ON findings(status);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_assigned_to ON findings(assigned_to_user_id);
CREATE INDEX idx_findings_run_severity ON findings(run_id, severity);
CREATE INDEX idx_findings_rule_status ON findings(rule_id, status);

-- schema_objects indexes
DROP INDEX IF EXISTS idx_schema_objects_db;
DROP INDEX IF EXISTS idx_schema_objects_type;
DROP INDEX IF EXISTS idx_schema_objects_name;
DROP INDEX IF EXISTS idx_schema_objects_optimization_status;

CREATE INDEX idx_schema_objects_db ON schema_objects(db_registry_id);
CREATE INDEX idx_schema_objects_type ON schema_objects(object_type);
CREATE INDEX idx_schema_objects_name ON schema_objects(object_name);
CREATE INDEX idx_schema_objects_optimization_status ON schema_objects(optimization_status);

-- versions indexes
DROP INDEX IF EXISTS idx_versions_object_id;
DROP INDEX IF EXISTS idx_versions_optimized;
DROP INDEX IF EXISTS idx_versions_changed_at;

CREATE INDEX idx_versions_object_id ON schema_object_versions(object_id);
CREATE INDEX idx_versions_optimized ON schema_object_versions(is_optimized);
CREATE INDEX idx_versions_changed_at ON schema_object_versions(changed_at);

-- finding_status_history indexes
DROP INDEX IF EXISTS idx_status_history_finding;
DROP INDEX IF EXISTS idx_status_history_changed_at;

CREATE INDEX idx_status_history_finding ON finding_status_history(finding_id);
CREATE INDEX idx_status_history_changed_at ON finding_status_history(changed_at);

-- comments indexes
DROP INDEX IF EXISTS idx_comments_finding_id;
DROP INDEX IF EXISTS idx_comments_user_id;

CREATE INDEX idx_comments_finding_id ON finding_comments(finding_id);
CREATE INDEX idx_comments_user_id ON finding_comments(user_id);

-- ============================================================================
-- STEP 9: Verification queries
-- ============================================================================

-- Verify migration
SELECT
    COUNT(*) as total_objects,
    SUM(COALESCE(char_length(current_definition), 0)) / 1024 / 1024 as total_mb,
    MAX(definition_size_bytes) as largest_object_bytes,
    AVG(definition_size_bytes) as avg_object_bytes
FROM schema_objects;

-- Show version history created
SELECT
    COUNT(*) as total_versions,
    COUNT(DISTINCT object_id) as objects_with_history
FROM schema_object_versions;

COMMIT;
