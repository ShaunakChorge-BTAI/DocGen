# Phase 3 Implementation Specification
## Reports + Help System

**Project:** DBAnalyser
**Phase:** 3 - Reports & Help System
**Duration:** 10 Working Days (2 weeks)
**Team Size:** 4-5 developers
**Date Created:** 2026-04-08
**Status:** Ready for Implementation

---

## Executive Summary

Phase 3 implements a comprehensive reporting system with scheduled report generation, historical trending, and an integrated help system with AI-powered content.

**Key Capabilities:**
- Custom report generation (PDF, Excel, HTML)
- Report scheduling and automation
- Historical data tracking and trending
- Help center with searchable articles
- AI-powered help suggestions
- Dashboard with key metrics

---

## Architecture Overview

```
┌─────────────────────────────────────┐
│      Browser (React)                │
│  ReportsPage + HelpCenter           │
└────────────────┬────────────────────┘
                 │ HTTP/REST
┌────────────────▼────────────────────┐
│      FastAPI Backend                │
│  /api/reports + /api/help           │
└────────────────┬────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│Report   │ │Help     │ │PostgreSQL│
│Template │ │Articles │ │(Results) │
│Engine   │ │Storage  │ │          │
└─────────┘ └─────────┘ └──────────┘
```

---

## Phase 3 Deliverables

### 1. Database Schema (reports_phase3_schema.sql)

**New Tables:**
```sql
-- Report templates and execution
CREATE TABLE report_templates (
  id SERIAL PRIMARY KEY,
  template_name VARCHAR(255),
  description TEXT,
  report_type VARCHAR(50),  -- dashboard, detailed, summary
  template_config JSONB,    -- columns, filters, sorting
  created_by_user_id INT,
  created_at TIMESTAMP,
  is_active BOOLEAN DEFAULT true
);

-- Scheduled report jobs
CREATE TABLE scheduled_reports (
  id SERIAL PRIMARY KEY,
  template_id INT REFERENCES report_templates(id),
  schedule_name VARCHAR(255),
  cron_expression VARCHAR(100),  -- "0 9 * * 1" = 9am Mondays
  recipients VARCHAR(500),       -- email list
  format VARCHAR(20),            -- pdf, excel, html
  is_active BOOLEAN DEFAULT true,
  next_run_at TIMESTAMP,
  last_run_at TIMESTAMP,
  created_by_user_id INT,
  created_at TIMESTAMP
);

-- Report execution history
CREATE TABLE report_executions (
  id SERIAL PRIMARY KEY,
  scheduled_report_id INT REFERENCES scheduled_reports(id),
  execution_date TIMESTAMP,
  row_count INT,
  execution_time_ms INT,
  file_path VARCHAR(500),
  status VARCHAR(50),  -- success, failed, pending
  error_message TEXT,
  recipients_notified VARCHAR(500),
  created_at TIMESTAMP
);

-- Help articles and knowledge base
CREATE TABLE help_articles (
  id SERIAL PRIMARY KEY,
  title VARCHAR(500) NOT NULL,
  slug VARCHAR(255) UNIQUE,
  content TEXT,
  category VARCHAR(100),  -- getting_started, features, troubleshooting, api
  tags VARCHAR(500),      -- comma-separated
  view_count INT DEFAULT 0,
  helpful_votes INT DEFAULT 0,
  created_by_user_id INT,
  updated_at TIMESTAMP,
  is_published BOOLEAN DEFAULT true,
  created_at TIMESTAMP
);

-- Help article comments/feedback
CREATE TABLE help_article_feedback (
  id SERIAL PRIMARY KEY,
  article_id INT REFERENCES help_articles(id),
  user_id INT,
  feedback_type VARCHAR(20),  -- helpful, not_helpful, comment
  feedback_text TEXT,
  created_at TIMESTAMP
);

-- Report metadata for dashboard
CREATE TABLE report_metrics (
  id SERIAL PRIMARY KEY,
  report_date DATE,
  total_findings INT,
  critical_findings INT,
  high_findings INT,
  medium_findings INT,
  low_findings INT,
  findings_resolved INT,
  avg_resolution_time_days DECIMAL(5,2),
  trend_pct DECIMAL(5,2),  -- month-over-month
  created_at TIMESTAMP
);

-- Historical trends for charts
CREATE TABLE finding_trends (
  id SERIAL PRIMARY KEY,
  date DATE,
  severity VARCHAR(20),
  count INT,
  cumulative_count INT,
  resolution_rate DECIMAL(5,2),
  created_at TIMESTAMP
);
```

**Indexes:**
- report_templates(is_active, created_at)
- scheduled_reports(template_id, is_active)
- report_executions(scheduled_report_id, execution_date DESC)
- help_articles(category, is_published)
- help_articles(slug)
- report_metrics(report_date DESC)
- finding_trends(date DESC, severity)

---

### 2. Backend Services

**reports_service.py (400 lines)**
```python
class ReportGenerator:
    def generate_report(template_id, filters, format='pdf'):
        # Query findings based on template
        # Format into PDF/Excel/HTML
        # Return file path

    def schedule_report(template_id, cron, recipients):
        # Create scheduled job
        # Set up cron execution

    def execute_scheduled_report(scheduled_id):
        # Generate report
        # Send to recipients
        # Log execution
```

**help_service.py (300 lines)**
```python
class HelpCenter:
    def search_articles(query, category=None):
        # Full-text search in help articles
        # Return matching articles with relevance

    def get_article(article_id):
        # Get article content
        # Increment view count

    def get_related_articles(article_id):
        # Find related articles by tags
```

---

### 3. Backend API Routes (reports_phase3.py - 600 lines)

**Endpoints:**

```
POST /reports/templates
  ├─ Create new report template
  └─ Body: {name, description, type, config}

GET /reports/templates
  ├─ List all templates
  └─ Filters: category, is_active

GET /reports/templates/{id}
  ├─ Get template details
  └─ Return: template config, sample data

POST /reports/execute
  ├─ Generate report immediately
  ├─ Body: {template_id, filters, format}
  └─ Returns: {file_path, row_count, time_ms}

GET /reports/history
  ├─ List execution history
  ├─ Pagination: limit=50, offset
  └─ Filters: status, date_range

POST /reports/schedule
  ├─ Create scheduled report
  ├─ Body: {template_id, cron, recipients, format}
  └─ Returns: {scheduled_id, next_run}

GET /reports/scheduled
  ├─ List scheduled reports
  └─ Filters: is_active

PATCH /reports/scheduled/{id}
  ├─ Update scheduled report
  └─ Body: {cron, recipients, is_active}

POST /reports/test-schedule
  ├─ Test cron expression
  ├─ Body: {cron_expression}
  └─ Returns: {next_3_run_dates}

GET /help/articles
  ├─ List articles with pagination
  ├─ Filters: category, is_published
  └─ Returns: {data, total, categories}

GET /help/articles/{id}
  ├─ Get article with related articles
  └─ Increments view count

POST /help/articles
  ├─ Create article (admin only)
  └─ Body: {title, content, category, tags}

PATCH /help/articles/{id}
  ├─ Update article
  └─ Body: {title, content, category, tags}

POST /help/search
  ├─ Full-text search articles
  ├─ Body: {query, category}
  └─ Returns: {results, relevance_scores}

POST /help/feedback
  ├─ Submit article feedback
  ├─ Body: {article_id, type, text}
  └─ Returns: {feedback_id}

GET /reports/dashboard
  ├─ Dashboard metrics
  └─ Returns: {trends, key_metrics, recent_reports}
```

---

### 4. Frontend Components (Phase3Pages.tsx - 800 lines)

**ReportsPage Component:**
- Report template selector
- Filter controls
- Execute now button
- Report history table
- Schedule new report button
- Scheduled reports management

**HelpCenter Component:**
- Search bar
- Category navigation
- Article listing
- Article detail view (5 sections)
- Related articles sidebar
- Feedback buttons
- Admin panel (publish/edit)

**Dashboard Component:**
- Key metrics cards (total, critical, resolved, etc.)
- Trend chart (line chart - 30 days)
- Recent reports list
- Scheduled reports next runs

---

### 5. Unit Tests (test_reports_phase3.py - 500 lines)

**Test Classes:**
- TestReportTemplates (8 tests)
- TestReportGeneration (10 tests)
- TestReportScheduling (8 tests)
- TestReportExecution (6 tests)
- TestHelpArticles (10 tests)
- TestHelpSearch (6 tests)
- TestHelpFeedback (4 tests)
- TestReportMetrics (5 tests)

**Total: 57 test cases**

---

## Implementation Timeline (10 Days)

**Days 1-2:** Database & Services
- Create migration script
- Implement ReportGenerator service
- Implement HelpCenter service

**Days 3-4:** Backend API
- Implement 15+ endpoints
- Add email notification (for scheduled reports)
- Add full-text search for help

**Days 5:** Frontend Components
- ReportsPage with all controls
- HelpCenter with search
- Dashboard metrics

**Days 6-7:** Integration & Testing
- E2E testing (report generation to email)
- Search functionality testing
- Scheduler testing

**Days 8-9:** Polish & Documentation
- Error handling refinement
- Performance optimization
- Complete all tests (57 tests)

**Day 10:** Staging & Sign-Off
- Deploy to staging
- Smoke tests
- Team sign-off

---

## Success Criteria

**Week 1 (Day 5):**
- ✅ Database migration successful
- ✅ Report generation working
- ✅ Help articles searchable
- ✅ 30+ tests passing
- ✅ Frontend components rendering

**Week 2 (Day 10):**
- ✅ Report scheduling functional
- ✅ Email notifications working
- ✅ Full-text search operational
- ✅ 57+ tests passing
- ✅ Dashboard metrics displaying
- ✅ Team sign-off obtained

---

## Dependencies

```python
# New packages
reportlab          # PDF generation
openpyxl           # Excel generation
apscheduler        # Job scheduling
python-cron        # Cron parsing
psycopg2-extras    # Full-text search
aiosmtplib         # Async email
```

---

## Files to Create

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `003_phase3_reports_schema.sql` | SQL | 400 | Database migration |
| `reports_service.py` | Python | 400 | Report generation |
| `help_service.py` | Python | 300 | Help system |
| `reports_phase3.py` | Python | 600 | API endpoints |
| `ReportsPage_Phase3.tsx` | React | 500 | Reports UI |
| `HelpCenter_Phase3.tsx` | React | 400 | Help UI |
| `test_reports_phase3.py` | Python | 500 | Unit tests |
| `PHASE_3_DEPLOYMENT_GUIDE.md` | Markdown | 300 | Deployment guide |

**Total:** ~3,400 lines of new code

---

**Version:** 1.0
**Status:** Ready for Implementation
**Created:** 2026-04-08
