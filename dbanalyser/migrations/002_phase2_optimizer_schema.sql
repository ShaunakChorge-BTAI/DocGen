-- Phase 2 SQL Optimizer Schema Migration
-- Adds tables for optimization suggestions, testing, metrics, and change requests
-- Created: 2026-04-08
-- Duration: ~15 seconds
-- Rollback: Available at end of this file

BEGIN;

-- ============================================================================
-- Step 1: Create optimization suggestions table
-- ============================================================================
CREATE TABLE schema_object_optimizations (
  id SERIAL PRIMARY KEY,
  finding_id INTEGER REFERENCES findings(id) ON DELETE CASCADE,
  object_name VARCHAR(500) NOT NULL,
  object_type VARCHAR(50),  -- Function, Procedure, View, etc.
  original_sql TEXT NOT NULL,
  suggested_sql TEXT NOT NULL,
  confidence_score DECIMAL(3,2),  -- 0.00 to 1.00
  estimated_improvement_pct INTEGER,  -- 5 to 95
  estimated_risk_level VARCHAR(50),  -- low, medium, high
  ollama_model VARCHAR(100),  -- model used (mistral, neural-chat, etc.)
  ollama_response_time_ms INTEGER,
  explanation TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by_user_id INTEGER,
  status VARCHAR(50) DEFAULT 'suggested',  -- suggested, tested, approved, cr_submitted
  download_count INTEGER DEFAULT 0,
  is_download_pending INTEGER DEFAULT 0
);

DROP INDEX IF EXISTS idx_optimizations_finding_id;
DROP INDEX IF EXISTS idx_optimizations_status;
DROP INDEX IF EXISTS idx_optimizations_created_at;
DROP INDEX IF EXISTS idx_optimizations_object_name;

CREATE INDEX idx_optimizations_finding_id ON schema_object_optimizations(finding_id);
CREATE INDEX idx_optimizations_status ON schema_object_optimizations(status);
CREATE INDEX idx_optimizations_created_at ON schema_object_optimizations(created_at DESC);
CREATE INDEX idx_optimizations_object_name ON schema_object_optimizations(object_name);

-- ============================================================================
-- Step 2: Create optimization test attempts table
-- ============================================================================
CREATE TABLE optimization_attempts (
  id SERIAL PRIMARY KEY,
  optimization_id INTEGER REFERENCES schema_object_optimizations(id) ON DELETE CASCADE,
  attempt_number INTEGER,  -- 1, 2, 3, etc.
  test_database VARCHAR(100) DEFAULT 'UAT',  -- UAT only in Phase 2
  test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(50),  -- success, failed, error, timeout
  original_execution_ms DECIMAL(10,2),  -- milliseconds
  optimized_execution_ms DECIMAL(10,2),
  improvement_pct DECIMAL(5,2),  -- calculated improvement
  original_row_count INTEGER,
  optimized_row_count INTEGER,
  data_integrity_verified INTEGER DEFAULT 0,  -- 1 = rows match
  error_message TEXT,
  created_by_user_id INTEGER,
  UNIQUE(optimization_id, attempt_number)
);

DROP INDEX IF EXISTS idx_attempts_optimization_id;
DROP INDEX IF EXISTS idx_attempts_test_date;
DROP INDEX IF EXISTS idx_attempts_status;

CREATE INDEX idx_attempts_optimization_id ON optimization_attempts(optimization_id);
CREATE INDEX idx_attempts_test_date ON optimization_attempts(test_date DESC);
CREATE INDEX idx_attempts_status ON optimization_attempts(status);

-- ============================================================================
-- Step 3: Create detailed performance metrics table
-- ============================================================================
CREATE TABLE optimization_metrics (
  id SERIAL PRIMARY KEY,
  attempt_id INTEGER REFERENCES optimization_attempts(id) ON DELETE CASCADE,
  metric_name VARCHAR(100),  -- CPU, Memory, RowsScanned, IndexUsed, etc.
  original_value VARCHAR(1000),
  optimized_value VARCHAR(1000),
  unit VARCHAR(50),  -- ms, rows, MB, %, count
  improvement_direction VARCHAR(20),  -- lower_better, higher_better
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP INDEX IF EXISTS idx_metrics_attempt_id;
DROP INDEX IF EXISTS idx_metrics_name;

CREATE INDEX idx_metrics_attempt_id ON optimization_metrics(attempt_id);
CREATE INDEX idx_metrics_name ON optimization_metrics(metric_name);

-- ============================================================================
-- Step 4: Create query plan storage table
-- ============================================================================
CREATE TABLE optimization_query_plans (
  id SERIAL PRIMARY KEY,
  attempt_id INTEGER REFERENCES optimization_attempts(id) ON DELETE CASCADE,
  plan_type VARCHAR(50),  -- original, optimized
  plan_text TEXT,  -- Full EXPLAIN/ANALYZE output
  estimated_rows INTEGER,
  actual_rows INTEGER,
  execution_time_ms DECIMAL(10,2),
  node_type VARCHAR(100),  -- Scan, Join, Sort, Filter, etc.
  node_detail TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP INDEX IF EXISTS idx_query_plans_attempt_id;
DROP INDEX IF EXISTS idx_query_plans_type;

CREATE INDEX idx_query_plans_attempt_id ON optimization_query_plans(attempt_id);
CREATE INDEX idx_query_plans_type ON optimization_query_plans(plan_type);

-- ============================================================================
-- Step 5: Create change request linking table
-- ============================================================================
CREATE TABLE optimization_change_requests (
  id SERIAL PRIMARY KEY,
  optimization_id INTEGER REFERENCES schema_object_optimizations(id) ON DELETE CASCADE,
  cr_id VARCHAR(100),  -- External CR number (JIRA/Azure Boards/etc.)
  cr_title TEXT,
  cr_description TEXT,
  implementation_notes TEXT,  -- How to apply the optimization
  submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  submitted_by_user_id INTEGER,
  status VARCHAR(50) DEFAULT 'submitted',  -- draft, submitted, approved, deployed, rejected
  approval_date TIMESTAMP,
  approved_by_user_id INTEGER,
  deployed_date TIMESTAMP,
  deployment_notes TEXT
);

DROP INDEX IF EXISTS idx_cr_optimization_id;
DROP INDEX IF EXISTS idx_cr_status;
DROP INDEX IF EXISTS idx_cr_id;

CREATE INDEX idx_cr_optimization_id ON optimization_change_requests(optimization_id);
CREATE INDEX idx_cr_status ON optimization_change_requests(status);
CREATE INDEX idx_cr_id ON optimization_change_requests(cr_id);

-- ============================================================================
-- Step 6: Add tracking columns to findings table (if not exist)
-- ============================================================================
-- Note: These may already exist from Phase 1
-- ALTER TABLE findings ADD COLUMN IF NOT EXISTS has_optimization INT DEFAULT 0;
-- ALTER TABLE findings ADD COLUMN IF NOT EXISTS optimization_id INT REFERENCES schema_object_optimizations(id);
-- ALTER TABLE findings ADD COLUMN IF NOT EXISTS cr_id VARCHAR(100);

-- ============================================================================
-- Step 7: Create optimization summary view
-- ============================================================================
CREATE VIEW v_optimization_summary AS
SELECT
  f.id AS finding_id,
  f.rule_id,
  f.object_name,
  COUNT(so.id) AS total_suggestions,
  SUM(CASE WHEN oa.status = 'success' THEN 1 ELSE 0 END) AS successful_tests,
  MAX(oa.improvement_pct)::DECIMAL(5,2) AS best_improvement_pct,
  AVG(oa.improvement_pct)::DECIMAL(5,2) AS avg_improvement_pct,
  COUNT(DISTINCT ocr.id) AS cr_count,
  MAX(so.created_at) AS last_optimization_date
FROM findings f
LEFT JOIN schema_object_optimizations so ON f.id = so.finding_id
LEFT JOIN optimization_attempts oa ON so.id = oa.optimization_id
LEFT JOIN optimization_change_requests ocr ON so.id = ocr.optimization_id
GROUP BY f.id, f.rule_id, f.object_name;

-- ============================================================================
-- Step 8: Verify schema
-- ============================================================================
-- These queries will show table counts:
-- SELECT COUNT(*) as optimization_count FROM schema_object_optimizations;
-- SELECT COUNT(*) as attempt_count FROM optimization_attempts;
-- SELECT COUNT(*) as metrics_count FROM optimization_metrics;
-- SELECT COUNT(*) as query_plans FROM optimization_query_plans;
-- SELECT COUNT(*) as cr_count FROM optimization_change_requests;

COMMIT;

-- ============================================================================
-- ROLLBACK PROCEDURE (if needed)
-- ============================================================================
-- To rollback this migration, execute:
/*
BEGIN;
DROP VIEW IF EXISTS v_optimization_summary;
DROP TABLE IF EXISTS optimization_change_requests CASCADE;
DROP TABLE IF EXISTS optimization_query_plans CASCADE;
DROP TABLE IF EXISTS optimization_metrics CASCADE;
DROP TABLE IF EXISTS optimization_attempts CASCADE;
DROP TABLE IF EXISTS schema_object_optimizations CASCADE;
COMMIT;
*/
