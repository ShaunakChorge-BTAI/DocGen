-- Phase 3 Reports + Help System Schema Migration
-- Date: 2026-04-08

BEGIN;

-- ============================================================================
-- PHASE 3: Report Templates & Execution
-- ============================================================================

CREATE TABLE report_templates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(255) NOT NULL,
    description TEXT,
    report_type VARCHAR(50),  -- dashboard, detailed, summary
    template_config JSONB,
    created_by_user_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE scheduled_reports (
    id SERIAL PRIMARY KEY,
    template_id INTEGER REFERENCES report_templates(id),
    schedule_name VARCHAR(255),
    cron_expression VARCHAR(100),
    recipients VARCHAR(500),
    format VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    next_run_at TIMESTAMP,
    last_run_at TIMESTAMP,
    created_by_user_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE report_executions (
    id SERIAL PRIMARY KEY,
    scheduled_report_id INTEGER REFERENCES scheduled_reports(id),
    execution_date TIMESTAMP,
    row_count INTEGER,
    execution_time_ms INTEGER,
    file_path VARCHAR(500),
    status VARCHAR(50),  -- success, failed, pending
    error_message TEXT,
    recipients_notified VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE report_metrics (
    id SERIAL PRIMARY KEY,
    report_date DATE,
    total_findings INTEGER,
    critical_findings INTEGER,
    high_findings INTEGER,
    medium_findings INTEGER,
    low_findings INTEGER,
    findings_resolved INTEGER,
    avg_resolution_time_days DECIMAL(5,2),
    trend_pct DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE finding_trends (
    id SERIAL PRIMARY KEY,
    date DATE,
    severity VARCHAR(20),
    count INTEGER,
    cumulative_count INTEGER,
    resolution_rate DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- PHASE 3: Help System & Knowledge Base
-- ============================================================================

CREATE TABLE help_articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    slug VARCHAR(255) UNIQUE,
    content TEXT,
    category VARCHAR(100),  -- getting_started, features, troubleshooting, api
    tags VARCHAR(500),
    view_count INTEGER DEFAULT 0,
    helpful_votes INTEGER DEFAULT 0,
    created_by_user_id INTEGER,
    updated_at TIMESTAMP,
    is_published BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE help_article_feedback (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES help_articles(id) ON DELETE CASCADE,
    user_id INTEGER,
    feedback_type VARCHAR(20),  -- helpful, not_helpful, comment
    feedback_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- PHASE 3: Indexes for Performance
-- ============================================================================

DROP INDEX IF EXISTS idx_report_templates_active;
DROP INDEX IF EXISTS idx_scheduled_reports_active;
DROP INDEX IF EXISTS idx_report_executions_scheduled;
DROP INDEX IF EXISTS idx_help_articles_category;
DROP INDEX IF EXISTS idx_help_articles_slug;
DROP INDEX IF EXISTS idx_report_metrics_date;
DROP INDEX IF EXISTS idx_finding_trends_date;

CREATE INDEX idx_report_templates_active ON report_templates(is_active, created_at DESC);
CREATE INDEX idx_scheduled_reports_active ON scheduled_reports(template_id, is_active);
CREATE INDEX idx_report_executions_scheduled ON report_executions(scheduled_report_id, execution_date DESC);
CREATE INDEX idx_report_executions_status ON report_executions(status);
CREATE INDEX idx_help_articles_category ON help_articles(category, is_published);
CREATE INDEX idx_help_articles_slug ON help_articles(slug);
CREATE INDEX idx_help_article_feedback_article ON help_article_feedback(article_id);
CREATE INDEX idx_report_metrics_date ON report_metrics(report_date DESC);
CREATE INDEX idx_finding_trends_date ON finding_trends(date DESC, severity);

COMMIT;
