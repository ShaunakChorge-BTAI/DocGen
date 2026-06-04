# Phase 2 Implementation Specification
## SQL Optimizer with Local Ollama Integration

**Project:** DBAnalyser
**Phase:** 2 - SQL Optimizer
**Duration:** 10 Working Days (2 weeks)
**Team Size:** 4-5 developers (1-2 backend, 1-2 frontend, 1 QA/DevOps)
**Date Created:** 2026-04-08
**Status:** Ready for Implementation

---

## Executive Summary

Phase 2 implements SQL optimization using **local Ollama** (no cloud), with:
- AI-powered SQL optimization suggestions
- UAT database impact analysis
- Download-only mode (no server deployment)
- Manual CR workflow for production changes
- Full audit trail and optimization history

**Key Constraint:** All optimization happens on UAT database; production untouched until user submits CR.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│            User Browser (React)                     │
│  OptimizerPage + OptimizationModal                  │
│  - Original SQL + Suggested Optimization            │
│  - UAT Test Results                                 │
│  - Download + Submit CR buttons                     │
└────────────────┬────────────────────────────────────┘
                 │ HTTP/REST
┌────────────────▼────────────────────────────────────┐
│         FastAPI Backend                             │
│  /optimizer endpoints:                              │
│  - POST /optimizer/suggest (call Ollama)            │
│  - POST /optimizer/test (run on UAT database)       │
│  - POST /optimizer/download (generate SQL file)     │
│  - GET /optimizer/history (optimization attempts)   │
│  - POST /optimizer/submit-cr (create change req)    │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────┴─────────┐
        │                  │
        ▼                  ▼
┌──────────────┐   ┌──────────────┐
│  Ollama      │   │ PostgreSQL   │
│  (Local)     │   │ (UAT + Prod) │
│  Port 11434  │   │              │
└──────────────┘   └──────────────┘
```

---

## Phase 2 Deliverables

### 1. Backend API Routes (optimizer_phase2.py)
**Endpoints:** 5 main + 3 helper = 8 total

```python
POST /optimizer/suggest
  ├─ Input: finding_id or object_name + SQL code
  ├─ Process: Send to Ollama for optimization suggestion
  ├─ Output: { suggestion, confidence, estimated_improvement_pct, risk_level }
  └─ Performance: ~5-15s (Ollama response time)

POST /optimizer/test
  ├─ Input: optimization_id, suggested_sql
  ├─ Process: Execute both original + optimized on UAT database
  ├─ Metrics:
  │  ├─ Original execution time (ms)
  │  ├─ Optimized execution time (ms)
  │  ├─ Query plan comparison
  │  ├─ Row count match (data integrity check)
  │  └─ Resource usage (CPU, Memory)
  ├─ Output: { passed: bool, metrics: {...}, error: null|string }
  └─ Performance: ~2-10s depending on query complexity

POST /optimizer/download
  ├─ Input: optimization_id, include_comparison: bool
  ├─ Output: SQL file download (suggested SQL + metadata)
  └─ Format: .sql file with both original and optimized versions

GET /optimizer/history/{finding_id}
  ├─ Output: All optimization attempts + test results
  └─ Format: [{ attempt_number, suggestion, test_date, metrics }]

POST /optimizer/submit-cr
  ├─ Input: optimization_id, description, implementation_notes
  ├─ Process: Create change request record
  ├─ Output: { cr_id, status: 'submitted', cr_link }
  └─ Links optimization to CR for tracking

GET /optimizer/suggestions (batch)
  ├─ Input: run_id, filter by untested|tested|approved
  ├─ Output: Paginated list of all optimizations for a run
  └─ Use case: Optimization dashboard/history view

GET /optimizer/metrics/{optimization_id}
  ├─ Output: Detailed performance metrics from test execution
  └─ Includes: Query plan, execution stats, resource usage

POST /optimizer/retry
  ├─ Input: optimization_id (retest with new Ollama suggestion)
  ├─ Process: Clear old suggestion, call Ollama again
  └─ Use case: Refine suggestions that didn't improve performance
```

### 2. Database Migration (002_phase2_optimizer_schema.sql)

**New Tables:**
```sql
-- Store optimization suggestions
CREATE TABLE schema_object_optimizations (
  id SERIAL PRIMARY KEY,
  finding_id INT FK findings.id,
  object_name VARCHAR(500),
  object_type VARCHAR(50),
  original_sql TEXT,
  suggested_sql TEXT,
  confidence_score DECIMAL(3,2),          -- 0.00 to 1.00
  estimated_improvement_pct INT,          -- 5 to 95
  estimated_risk_level VARCHAR(50),       -- low, medium, high
  ollama_model VARCHAR(100),              -- model used
  ollama_response_time_ms INT,
  created_at TIMESTAMP,
  created_by_user_id INT FK users.id,
  status VARCHAR(50) DEFAULT 'suggested', -- suggested, tested, approved, cr_submitted
  is_download INT,
  download_count INT DEFAULT 0
);

-- Track test executions on UAT
CREATE TABLE optimization_attempts (
  id SERIAL PRIMARY KEY,
  optimization_id INT FK schema_object_optimizations.id,
  attempt_number INT,
  test_database VARCHAR(100),             -- 'UAT' only in Phase 2
  test_date TIMESTAMP,
  status VARCHAR(50),                     -- 'success', 'failed', 'error'
  original_execution_ms DECIMAL(10,2),
  optimized_execution_ms DECIMAL(10,2),
  improvement_pct DECIMAL(5,2),
  data_integrity_verified INT,            -- 1 = rows match
  error_message TEXT,
  created_by_user_id INT FK users.id
);

-- Detailed performance metrics
CREATE TABLE optimization_metrics (
  id SERIAL PRIMARY KEY,
  attempt_id INT FK optimization_attempts.id,
  metric_name VARCHAR(100),
  original_value VARCHAR(1000),
  optimized_value VARCHAR(1000),
  unit VARCHAR(50),                       -- ms, rows, MB, %
  improvement_direction VARCHAR(20)       -- 'lower_better', 'higher_better'
);

-- Query plans (before/after)
CREATE TABLE optimization_query_plans (
  id SERIAL PRIMARY KEY,
  attempt_id INT FK optimization_attempts.id,
  plan_type VARCHAR(50),                  -- 'original', 'optimized'
  plan_text TEXT,
  estimated_rows INT,
  actual_rows INT,
  execution_time_ms DECIMAL(10,2),
  node_type VARCHAR(100),                 -- 'Scan', 'Join', 'Sort', etc.
  node_detail TEXT
);

-- Change requests linked to optimizations
CREATE TABLE optimization_change_requests (
  id SERIAL PRIMARY KEY,
  optimization_id INT FK schema_object_optimizations.id,
  cr_id VARCHAR(100),                     -- external CR number
  cr_title TEXT,
  cr_description TEXT,
  implementation_notes TEXT,
  submitted_date TIMESTAMP,
  submitted_by_user_id INT FK users.id,
  status VARCHAR(50),                     -- 'draft', 'submitted', 'approved', 'deployed', 'rejected'
  approval_date TIMESTAMP,
  deployed_date TIMESTAMP
);
```

**Indexes:**
```sql
-- Performance indexes for optimization queries
CREATE INDEX idx_optimizations_finding_id ON schema_object_optimizations(finding_id);
CREATE INDEX idx_optimizations_status ON schema_object_optimizations(status);
CREATE INDEX idx_optimizations_created_at ON schema_object_optimizations(created_at DESC);
CREATE INDEX idx_attempts_optimization_id ON optimization_attempts(optimization_id);
CREATE INDEX idx_attempts_test_date ON optimization_attempts(test_date DESC);
CREATE INDEX idx_metrics_attempt_id ON optimization_metrics(attempt_id);
CREATE INDEX idx_query_plans_attempt_id ON optimization_query_plans(attempt_id);
CREATE INDEX idx_cr_optimization_id ON optimization_change_requests(optimization_id);
```

### 3. Backend Ollama Integration (ollama_service.py)

```python
class OllamaOptimizer:
    """Local Ollama integration for SQL optimization"""

    def __init__(self, host="localhost", port=11434, model="mistral"):
        self.host = host
        self.port = port
        self.model = model
        self.base_url = f"http://{host}:{port}"

    async def optimize_sql(self,
        sql_code: str,
        object_type: str,
        rule_id: str,
        issue_description: str
    ) -> dict:
        """
        Call Ollama to suggest SQL optimization

        Returns:
        {
            "suggested_sql": "optimized SQL code",
            "explanation": "why this is better",
            "confidence_score": 0.85,
            "estimated_improvement_pct": 35,
            "estimated_risk_level": "low",
            "response_time_ms": 8500
        }
        """
        prompt = f"""
        Optimize this {object_type} SQL code.

        Current Issue: {issue_description} ({rule_id})

        Original SQL:
        {sql_code}

        Provide:
        1. Optimized SQL code
        2. Brief explanation of changes
        3. Confidence (0-1) that this improves performance
        4. Estimated performance improvement (%)
        5. Risk level (low/medium/high)

        Format as JSON.
        """

        # Call Ollama local API
        # Returns suggested_sql, explanation, confidence, improvement, risk
```

### 4. Frontend Optimizer Page (OptimizerPage_Phase2.tsx)

**Components:**
- `OptimizerPage` - Main container with tabs
- `SuggestTab` - Input SQL, call /suggest, show results
- `TestTab` - Run UAT tests, show metrics comparison
- `HistoryTab` - All optimization attempts for current finding
- `CRTab` - Submit change request with CR details
- `OptimizationComparisonView` - Side-by-side SQL comparison
- `MetricsTableView` - Performance metrics table

**Features:**
- Input original SQL (or paste from finding)
- Call "Get Suggestion" button → Ollama response
- Show confidence score, risk level, estimated improvement
- "Test on UAT" button → Execute both queries, show results
- Side-by-side diff of original vs optimized
- Performance metrics table
- "Download" button → Generate .sql file
- "Submit CR" button → Create change request
- History of all attempts for this finding

### 5. Database Utilities (optimization_db_utils.py)

```python
async def execute_on_database(
    sql: str,
    database: str,  # 'uat' or 'prod'
    timeout_seconds: int = 30
) -> dict:
    """
    Execute SQL on specified database
    Returns: { execution_time_ms, row_count, error }
    """

async def compare_results(
    original_result: dict,
    optimized_result: dict
) -> dict:
    """
    Compare two query execution results
    Returns: { improvement_pct, metrics, data_integrity_ok }
    """

async def get_query_plan(
    sql: str,
    database: str
) -> dict:
    """
    Get EXPLAIN/ANALYZE output
    Returns: { plan, estimated_rows, actual_rows, execution_time }
    """
```

### 6. Unit Tests (test_optimizer_phase2.py)

**Test Classes:**
- `TestOptimizerSuggest` - Ollama integration tests
- `TestOptimizerTest` - UAT database execution tests
- `TestOptimizationMetrics` - Metrics calculation tests
- `TestChangeRequest` - CR submission tests
- `TestQueryComparison` - Query result comparison tests

**Test Cases:**
- Ollama API availability check
- Optimization suggestion generation
- UAT database connectivity
- Query execution and timing
- Data integrity verification
- Query plan comparison
- CR submission and linking
- History retrieval
- Error handling (timeout, invalid SQL, etc.)

**Coverage Target:** 25+ test cases

### 7. Frontend Components (OptimizerPage_Phase2.tsx)

**Layout:**
```
┌─────────────────────────────────────────┐
│  OptimizerPage (450 lines)              │
│  ┌─────────────────────────────────────┐
│  │ Tabs: Suggest | Test | History | CR  │
│  └─────────────────────────────────────┘
│
│  [Suggest Tab]
│  ├─ Input: SQL code area (read-only or editable)
│  ├─ Button: "Get Optimization Suggestion"
│  ├─ Result area:
│  │  ├─ Confidence score badge
│  │  ├─ Estimated improvement badge
│  │  ├─ Risk level badge (color-coded)
│  │  ├─ Explanation text
│  │  └─ Suggested SQL (syntax highlighted)
│  └─ Button: "Test on UAT" → Tab 2
│
│  [Test Tab]
│  ├─ Original execution time (ms)
│  ├─ Optimized execution time (ms)
│  ├─ Metrics table:
│  │  ├─ Metric name | Original | Optimized | Improvement
│  │  └─ Data integrity verification status
│  ├─ Query plan comparison (expandable)
│  └─ Button: "Download" or "Submit CR"
│
│  [History Tab]
│  ├─ List of all optimization attempts
│  │  ├─ Attempt #1: Date, Status, Improvement %, Action buttons
│  │  ├─ Attempt #2: ...
│  │  └─ Attempt #N: ...
│  └─ Button: "Retry Optimization" (new suggestion from Ollama)
│
│  [CR Tab]
│  ├─ CR Form:
│  │  ├─ Title input
│  │  ├─ Description textarea
│  │  ├─ Implementation notes
│  │  └─ Button: "Submit Change Request"
│  └─ Status: Draft | Submitted | Approved | Deployed
│
└─────────────────────────────────────────┘
```

---

## Implementation Timeline (10 Days)

### Day 1-2: Database & Backend Foundation
- [ ] Create `002_phase2_optimizer_schema.sql` (7 tables, 10 indexes)
- [ ] Create `ollama_service.py` with OllamaOptimizer class
- [ ] Create `optimization_db_utils.py` with execution functions
- [ ] Unit test database migrations

### Day 3-4: Backend API Endpoints
- [ ] Create `optimizer_phase2.py` with 8 endpoints
- [ ] Implement Ollama integration
- [ ] Implement UAT database execution
- [ ] Implement metrics calculation
- [ ] Unit test all endpoints (minimum 15 test cases)

### Day 5: Frontend Components
- [ ] Create `OptimizerPage_Phase2.tsx` (450+ lines)
- [ ] Create all sub-components
- [ ] Implement tab navigation
- [ ] Wire up API calls via React Query
- [ ] Add syntax highlighting for SQL

### Day 6-7: Integration & Testing
- [ ] E2E workflow testing (suggest → test → download → CR)
- [ ] Performance testing (Ollama response time, UAT queries)
- [ ] Error handling and edge cases
- [ ] Mobile responsiveness

### Day 8-9: Polish & Documentation
- [ ] Code cleanup and optimization
- [ ] Add error messages and user feedback
- [ ] Complete unit test suite (25+ tests)
- [ ] Documentation updates

### Day 10: Staging & Sign-Off
- [ ] Deploy to staging environment
- [ ] Smoke tests
- [ ] Performance validation
- [ ] Team sign-off

---

## Success Criteria

### Week 1 (Day 5)
- ✅ Database migration successful (7 tables, 10 indexes)
- ✅ Ollama integration working (receives suggestions in <15s)
- ✅ UAT database queries execute successfully
- ✅ API endpoints functional (all 8 endpoints)
- ✅ Basic React UI renders
- ✅ 15+ unit tests passing

### Week 2 (Day 10)
- ✅ Full E2E workflow complete
- ✅ Optimization suggestions tested on UAT
- ✅ Metrics calculated and displayed
- ✅ Download functionality working
- ✅ CR submission functional
- ✅ 25+ unit tests passing
- ✅ Performance targets met (<15s suggestion, <10s test)
- ✅ Team sign-off obtained

---

## Ollama Setup & Configuration

### Prerequisites
```bash
# Install Ollama from https://ollama.ai
# Download model (mistral is lightweight, good for SQL):
ollama pull mistral      # ~7GB
# or
ollama pull neural-chat  # ~5GB (faster, smaller)

# Start Ollama service
ollama serve             # Runs on localhost:11434
```

### Testing Ollama Locally
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Optimize: SELECT * FROM users WHERE id = 1",
  "stream": false
}'
```

### Model Selection for SQL
- **mistral:** Better SQL understanding, ~8GB
- **neural-chat:** Faster responses, ~5GB
- **dolphin-mixtral:** Excellent SQL, ~27GB (if resources allow)

---

## Dependencies

### Backend
```python
# New packages
ollama          # Python client for Ollama
sqlalchemy      # Already have
psycopg2        # Already have
pandas          # For metrics comparison
numpy           # For statistics
```

### Frontend
```json
{
  "react-syntax-highlighter": "^15.x",
  "diff-match-patch": "^20200713",
  "@tanstack/react-query": "^4.x"
}
```

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Ollama not installed | Medium | High | Install guide in docs, fallback to demo mode |
| Ollama slow response | Medium | Medium | Timeout after 30s, show "Try again" |
| UAT DB unavailable | Low | Critical | Health check endpoint, clear error message |
| SQL injection in test | Low | Critical | Parameterized queries only, no direct SQL |
| Query timeout | Medium | Low | 30s timeout with user notification |
| Large query results | Medium | Low | Limit result rows to 10,000 |

---

## API Contract (OpenAPI)

```yaml
/optimizer/suggest:
  post:
    summary: Get SQL optimization suggestion from Ollama
    requestBody:
      finding_id: int
      sql_code: string
      object_type: string
      rule_id: string
    responses:
      200:
        schema:
          suggestion_id: string
          suggested_sql: string
          confidence_score: number  # 0-1
          estimated_improvement_pct: int
          estimated_risk_level: string
          explanation: string

/optimizer/test:
  post:
    summary: Test optimization on UAT database
    requestBody:
      optimization_id: string
      suggested_sql: string
    responses:
      200:
        schema:
          success: boolean
          original_time_ms: number
          optimized_time_ms: number
          improvement_pct: number
          data_integrity_ok: boolean
          metrics: array

/optimizer/download:
  post:
    summary: Download optimized SQL as file
    requestBody:
      optimization_id: string
      include_comparison: boolean
    responses:
      200:
        type: file
        content: application/sql

/optimizer/submit-cr:
  post:
    summary: Submit optimization as change request
    requestBody:
      optimization_id: string
      cr_title: string
      cr_description: string
    responses:
      201:
        schema:
          cr_id: string
          status: string
```

---

## Known Limitations (Phase 2)

- ❌ No automatic deployment (manual CR process)
- ❌ No rollback automation
- ❌ No production database optimization (UAT only)
- ❌ Limited to SQL Server/PostgreSQL syntax
- ❌ No advanced indexing suggestions (Phase 3)
- ❌ No historical performance tracking (Phase 4)

These will be addressed in Phase 3+.

---

## Files to Create

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `002_phase2_optimizer_schema.sql` | SQL | 400 | 7 new tables, 10 indexes |
| `optimizer_phase2.py` | Python | 500 | 8 API endpoints |
| `ollama_service.py` | Python | 200 | Ollama integration |
| `optimization_db_utils.py` | Python | 200 | Database utilities |
| `OptimizerPage_Phase2.tsx` | React | 450 | Main UI component |
| `test_optimizer_phase2.py` | Python | 400 | 25+ unit tests |
| `PHASE_2_DEPLOYMENT_GUIDE.md` | Markdown | 300 | Deployment instructions |
| `PHASE_2_IMPLEMENTATION_SUMMARY.md` | Markdown | 200 | Summary & checklist |

**Total:** ~2,700 lines of new code/documentation

---

## Getting Help

- **Ollama questions:** See ollama_service.py inline docs
- **Database schema:** See 002_phase2_optimizer_schema.sql comments
- **API contract:** See OpenAPI spec above
- **Daily standup:** 9:30 AM

---

**Version:** 1.0
**Status:** Ready for Implementation
**Created:** 2026-04-08
