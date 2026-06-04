# Phase 5 Implementation Specification
## Unified Assessment Wizard

**Project:** DBAnalyser
**Phase:** 5 - Unified Assessment Wizard
**Duration:** 10 Working Days (1 week)
**Team Size:** 3-4 developers
**Date Created:** 2026-04-08
**Status:** Ready for Implementation

---

## Executive Summary

Phase 5 unifies the assessment process into a single, guided wizard that walks users through database selection, scanning, and result analysis in one cohesive flow.

**Key Capabilities:**
- Step-by-step assessment wizard
- Database selection and configuration
- Scan execution with real-time progress
- Result analysis and actionable insights
- Assessment history and comparison
- Recommendations engine

---

## Phase 5 Deliverables

### 1. Database Schema (005_phase5_wizard_schema.sql - 400 lines)

**New Tables:**
```sql
-- Assessment templates and presets
CREATE TABLE assessment_templates (
  id SERIAL PRIMARY KEY,
  template_name VARCHAR(255),
  description TEXT,
  scope_rules JSONB,  -- which checks to run
  filters JSONB,      -- object types, schemas
  is_public BOOLEAN DEFAULT false,
  created_by_user_id INT,
  created_at TIMESTAMP
);

-- Assessment execution state (for multi-step wizard)
CREATE TABLE assessment_sessions (
  id SERIAL PRIMARY KEY,
  session_token VARCHAR(255) UNIQUE,
  user_id INT,
  current_step INT,  -- 1=select_db, 2=configure, 3=scan, 4=results
  selected_databases JSONB,  -- array of db_registry_ids
  assessment_config JSONB,   -- user preferences
  scan_progress INT DEFAULT 0,  -- 0-100
  status VARCHAR(50) DEFAULT 'in_progress',  -- in_progress, completed, failed
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  created_at TIMESTAMP
);

-- Assessment execution with results
CREATE TABLE assessment_runs (
  id SERIAL PRIMARY KEY,
  session_id INT REFERENCES assessment_sessions(id),
  run_date TIMESTAMP,
  databases_scanned INT,
  objects_scanned INT,
  findings_count INT,
  critical_count INT,
  execution_time_ms INT,
  status VARCHAR(50),  -- success, failed, partial
  created_at TIMESTAMP
);

-- Assessment comparison (same db across time)
CREATE TABLE assessment_comparisons (
  id SERIAL PRIMARY KEY,
  database_id INT REFERENCES db_registry(id),
  baseline_run_id INT REFERENCES assessment_runs(id),
  current_run_id INT REFERENCES assessment_runs(id),
  comparison_date TIMESTAMP,
  findings_improved INT,
  findings_regressed INT,
  findings_new INT,
  critical_increase INT,
  created_at TIMESTAMP
);

-- Smart recommendations based on findings
CREATE TABLE assessment_recommendations (
  id SERIAL PRIMARY KEY,
  finding_id INT REFERENCES findings(id),
  recommendation_type VARCHAR(50),  -- immediate, priority, future
  recommendation_text TEXT,
  implementation_effort VARCHAR(20),  -- low, medium, high
  estimated_benefit VARCHAR(20),     -- low, medium, high
  priority_score INT,  -- 1-100
  created_at TIMESTAMP
);
```

---

### 2. Backend Services

**assessment_wizard_service.py (500 lines)**
```python
class AssessmentWizard:
    def start_session(user_id, template_id=None):
        # Create assessment session
        # Set step to 1
        # Return session token

    def get_session_state(session_token):
        # Return current wizard state
        # Include: databases, config, progress, current_step

    def select_databases(session_token, database_ids):
        # Validate selected databases
        # Update session
        # Move to step 2

    def configure_assessment(session_token, config):
        # Save user preferences
        # Set scope rules
        # Move to step 3

    def start_scan(session_token):
        # Execute assessment
        # Track progress
        # Move to step 4

    def get_scan_progress(session_token):
        # Return: current progress %, ETA, status

    def get_results(session_token):
        # Return assessment results
        # Include findings, metrics, recommendations
```

**recommendations_engine.py (300 lines)**
```python
class RecommendationEngine:
    def generate_recommendations(assessment_run_id):
        # Analyze findings
        # Prioritize by impact
        # Generate actionable recommendations

    def get_quick_wins(findings):
        # Low effort, high impact items
        # Return prioritized list
```

---

### 3. Backend API Routes (wizard_phase5.py - 600 lines)

**Endpoints:**
```
POST /wizard/start
  ├─ Start new assessment wizard
  ├─ Body: {template_id?}
  └─ Returns: {session_token, current_step}

GET /wizard/session/{token}
  ├─ Get current wizard state
  └─ Returns: {step, databases, config, progress}

POST /wizard/select-databases
  ├─ Select databases for assessment
  ├─ Body: {session_token, database_ids}
  └─ Returns: {databases_selected, next_step}

POST /wizard/configure
  ├─ Configure assessment parameters
  ├─ Body: {session_token, config}
  └─ Returns: {configuration_saved, next_step}

POST /wizard/start-scan
  ├─ Begin assessment scan
  ├─ Body: {session_token}
  └─ Returns: {scan_id, progress_url}

GET /wizard/progress/{session_token}
  ├─ Get scan progress
  └─ Returns: {percentage, status, eta, objects_scanned}

POST /wizard/cancel
  ├─ Cancel assessment
  └─ Cleanup session state

GET /wizard/results/{session_token}
  ├─ Get assessment results
  └─ Returns: {findings, metrics, recommendations}

POST /wizard/compare
  ├─ Compare current vs baseline
  ├─ Body: {database_id, baseline_run_id}
  └─ Returns: {improvements, regressions, net_change}

GET /wizard/recommendations/{run_id}
  ├─ Get smart recommendations
  ├─ Filters: type, priority, effort
  └─ Returns: {quick_wins, priority_items, future_work}

GET /wizard/history/{database_id}
  ├─ Assessment history
  ├─ Pagination: limit=20
  └─ Returns: {past_assessments, trends}

POST /wizard/templates
  ├─ List assessment templates
  └─ Returns: {templates, descriptions}
```

---

### 4. Frontend Components (WizardPage_Phase5.tsx - 1000 lines)

**AssessmentWizard Component:**
- Step indicator (1-4 with progress bar)
- Database selection step (multi-select with filters)
- Configuration step (assessment scope, rules)
- Scan execution step (real-time progress)
- Results display step (findings, metrics, recommendations)
- Navigation buttons (Previous/Next, Skip optional)

**Results Display:**
- Finding summary cards
- Comparison vs baseline
- Recommendations section
- Export results option
- Schedule follow-up assessment

**WizardState Management:**
- Persist wizard state to session storage
- Allow resuming interrupted assessments
- Validation before moving to next step

---

### 5. Unit Tests (test_wizard_phase5.py - 500 lines)

**Test Classes:**
- TestWizardSession (8 tests)
- TestDatabaseSelection (6 tests)
- TestAssessmentConfiguration (8 tests)
- TestScanExecution (10 tests)
- TestProgressTracking (6 tests)
- TestResultsGeneration (8 tests)
- TestComparison (6 tests)
- TestRecommendations (8 tests)
- TestWizardNavigation (6 tests)

**Total: 66 test cases**

---

## Implementation Timeline (10 Days)

**Days 1-2:** Database & Services
- Migration script
- Assessment wizard service
- Recommendations engine

**Days 3:** Backend API
- Wizard endpoints
- Progress tracking
- Recommendations API

**Days 4-5:** Frontend
- Multi-step wizard UI
- Progress indicator
- Results display

**Days 6-7:** Integration
- End-to-end wizard flow
- State persistence
- Error recovery

**Days 8-9:** Testing & Polish
- 66 unit tests
- Edge case handling
- Performance optimization

**Day 10:** Staging & Sign-Off

---

## User Journey

1. **Start:** User clicks "New Assessment"
2. **Step 1:** Select databases from list (multi-select)
3. **Step 2:** Configure assessment scope (object types, schemas, rules)
4. **Step 3:** Execute scan (real-time progress, ETA)
5. **Step 4:** View results (findings, metrics, recommendations)
6. **Compare:** See improvements vs last assessment
7. **Action:** Create CRs from recommendations

---

## Success Criteria

**Week 1 (Day 5):**
- ✅ Wizard UI rendering (all 4 steps)
- ✅ Database selection working
- ✅ Scan execution functional
- ✅ 30+ tests passing

**Week 2 (Day 10):**
- ✅ Multi-step flow complete
- ✅ Progress tracking working
- ✅ Results display functional
- ✅ Comparisons working
- ✅ Recommendations engine active
- ✅ 66+ tests passing
- ✅ Team sign-off obtained

---

**Version:** 1.0
**Status:** Ready for Implementation
