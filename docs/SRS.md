# Software Requirements Specification (SRS)
## DBAnalyser — Enterprise SQL Server Code Quality & Compliance Analyser
### Version 2.0.0 | LTFS Technology | March 2026

---

## Table of Contents

1. Introduction
2. Overall Description
3. Functional Requirements
4. Non-Functional Requirements
5. System Architecture
6. Data Requirements
7. Interface Requirements
8. Rule Engine Specification
9. Compliance Pack Specification
10. Constraints and Assumptions
11. Phase C & D Functional Requirements

---

## 1. Introduction

### 1.1 Purpose
This document specifies the software requirements for DBAnalyser v2.0.0, an enterprise platform for automated SQL Server code-quality analysis, security auditing, compliance checking, and performance trend monitoring. It is intended for development teams, QA engineers, database administrators, and compliance officers at LTFS.

### 1.2 Scope
DBAnalyser analyses SQL objects (Stored Procedures, Views, Tables, Functions, Triggers) sourced either from file trees or live SQL Server connections. It applies a configurable rule engine, produces graded findings (Critical / High / Medium / Low), persists results to PostgreSQL, and exposes them via a CLI, REST API, and Streamlit dashboard.

### 1.3 Definitions

| Term | Definition |
|------|------------|
| SQL Object | A database artifact: Stored Procedure, View, Table, Function, or Trigger |
| Finding | A single rule violation detected in a SQL object |
| Run | One complete analysis execution across one or more databases |
| Health Score | Numeric score 0–100 derived from finding severity counts |
| Compliance Pack | A named set of rules targeting a specific regulatory framework (SOX, GDPR, RBI) |
| Custom Rule | A user-defined rule specified in a YAML file, loaded alongside built-in rules |
| DB Registry | PostgreSQL table tracking all registered SQL Server databases |
| Trend | Time-series of health scores per database across multiple runs |
| Scheduled Task | A named recurring analysis task stored in the `scheduled_tasks` table and fired by the built-in scheduler |
| JWT | JSON Web Token — used for stateless API authentication when `auth.enabled: true` |

### 1.4 References
- analysis_config.yaml — runtime configuration schema
- dbanalyser/db/schema.sql — PostgreSQL persistence schema
- pyproject.toml — dependency manifest
- CLAUDE.md — developer architecture guide

---

## 2. Overall Description

### 2.1 Product Perspective
DBAnalyser operates as a standalone Python application with five interaction modes:
1. **CLI** (`dbanalyser` command) — batch analysis and administration
2. **REST API** (FastAPI, port 8000) — programmatic access and CI/CD integration
3. **Dashboard** (Streamlit, port 8501) — interactive visualisation
4. **Built-in Scheduler** — background thread within the API process for unattended periodic scans
5. **Docker** — containerised deployment via `Dockerfile` + `docker-compose.yml`

### 2.2 Product Functions Summary
- Scan SQL objects from filesystem (`.sql`, `.ddl`) or live SQL Server via ODBC
- Apply 62 built-in rules across 11 categories, plus YAML-driven custom rules
- Apply optional compliance packs: SOX (6 rules), GDPR (6 rules), RBI (6 rules)
- Persist findings and health scores to PostgreSQL
- Track health score trends over time per registered database
- Generate reports in Excel, HTML, CSV, and JSON
- Expose all data via authenticated REST API
- Provide a multi-database estate dashboard with trend charts
- Support CI/CD health-gate checks via HTTP endpoint
- Author custom rules via YAML without writing Python
- Send Slack / Teams webhook alerts after analysis runs
- Schedule recurring analysis tasks via a built-in cron-like engine
- Authenticate API users via JWT RBAC
- Deploy via Docker with a single `docker compose up` command

### 2.3 Users

| User Type | Interaction Mode | Primary Use Case |
|-----------|-----------------|------------------|
| DBA | CLI + Dashboard | Run analysis, review findings, track trends |
| Developer | CLI | Local quality gate before code review |
| CI/CD Pipeline | REST API | Automated quality gate on deployment |
| Compliance Officer | Dashboard + Reports | Audit SOX/GDPR/RBI compliance posture |
| Platform Admin | CLI (`init-db`, `db sync`) | Infrastructure setup and DB registry management |

### 2.4 Operating Environment
- **OS**: Windows Server 2016+ or Windows 10+ (primary); Linux (secondary via WSL/Docker)
- **Python**: 3.10 or higher
- **PostgreSQL**: 13 or higher (for persistence; optional for file-mode analysis)
- **SQL Server**: 2016 or higher (for live-DB mode via ODBC)
- **ODBC Driver**: Microsoft ODBC Driver 17 for SQL Server

---

## 3. Functional Requirements

### 3.1 Source Scanning

| ID | Requirement |
|----|-------------|
| FR-SC-01 | The system SHALL scan `.sql` and `.ddl` files recursively from a configured file path |
| FR-SC-02 | The system SHALL connect to a live SQL Server via pyodbc and extract object DDL |
| FR-SC-03 | The system SHALL classify each SQL object into one of: Stored Procedure, View, Table, Function, Trigger |
| FR-SC-04 | The system SHALL extract the schema name from DDL (default: `dbo`) |
| FR-SC-05 | The system SHALL respect `scope.object_types`, `scope.schemas`, `scope.exclude_schemas`, and `scope.exclude_patterns` filters |
| FR-SC-06 | The system SHALL skip objects exceeding `scope.max_object_size_kb` |

### 3.2 Rule Engine

| ID | Requirement |
|----|-------------|
| FR-RE-01 | The system SHALL apply all enabled rules from the rule registry to each SQL object |
| FR-RE-02 | Each finding SHALL carry: rule_id, category, severity (Critical/High/Medium/Low), issue text, recommendation, line number, optional snippet |
| FR-RE-03 | Rules SHALL be filterable by category via `analysis.categories` toggles |
| FR-RE-04 | The system SHALL execute rules concurrently using a configurable thread pool |
| FR-RE-05 | Individual rule failures SHALL be logged and skipped without aborting the analysis |
| FR-RE-06 | Compliance packs SHALL be loaded dynamically based on `compliance.enabled_packs` |
| FR-RE-07 | The system SHALL support caller-supplied rule override lists for testing purposes |

### 3.3 Health Scoring

| ID | Requirement |
|----|-------------|
| FR-HS-01 | Health score = `100 - (Critical×5) - (High×2) - (Medium×0.5) - (Low×0.1)`, minimum 0.0 |
| FR-HS-02 | Health score SHALL be computed at both object level and aggregate run level |
| FR-HS-03 | Health scores SHALL be persisted per run and per database in the `health_trend` table |

### 3.4 Persistence

| ID | Requirement |
|----|-------------|
| FR-DB-01 | The system SHALL persist run metadata to the `runs` table |
| FR-DB-02 | The system SHALL persist all findings to the `findings` table via bulk insert |
| FR-DB-03 | The system SHALL upsert database registry entries in `db_registry` |
| FR-DB-04 | The system SHALL upsert one health trend row per run per database |
| FR-DB-05 | The system SHALL update `db_registry.last_run_at` and `last_health` after each run |
| FR-DB-06 | Persistence SHALL be optional — `--no-persist` flag skips all PostgreSQL writes |
| FR-DB-07 | The system SHALL create the full PostgreSQL schema via `dbanalyser init-db` |

### 3.5 Reporting

| ID | Requirement |
|----|-------------|
| FR-RP-01 | The system SHALL generate Excel reports (.xlsx) with a Findings sheet and a Summary sheet |
| FR-RP-02 | The system SHALL generate HTML reports with findings table |
| FR-RP-03 | The system SHALL generate CSV exports of findings |
| FR-RP-04 | The system SHALL generate JSON reports with run metadata and findings array |
| FR-RP-05 | Reports SHALL be downloadable on-demand via the REST API |
| FR-RP-06 | The `dbanalyser compliance-report` command SHALL generate a report containing only compliance findings (SOX/GDPR/RBI), in Excel, JSON, or CSV format |

### 3.6 REST API

| ID | Requirement |
|----|-------------|
| FR-API-01 | The system SHALL expose a FastAPI application on a configurable host and port |
| FR-API-02 | All routes (except `/health` and `/`) SHALL support optional API key authentication |
| FR-API-03 | Authentication SHALL accept the key via `X-API-Key` request header or `?api_key=` query parameter |
| FR-API-04 | If no API key is configured the API SHALL operate in open mode |
| FR-API-05 | The system SHALL provide Swagger UI at `/docs` and ReDoc at `/redoc` |
| FR-API-06 | The system SHALL support asynchronous analysis triggering via `POST /runs/trigger` |
| FR-API-07 | The system SHALL track async job status (queued / running / done / failed) via `GET /runs/jobs/{job_id}` |
| FR-API-08 | The health-gate endpoint SHALL return HTTP 200 (pass) or HTTP 422 (fail) based on configurable thresholds |
| FR-API-09 | The findings status endpoint SHALL support lifecycle states: open, acknowledged, fixed, suppressed, wontfix |
| FR-API-10 | A compliance health-gate endpoint `GET /runs/{run_id}/health-gate` SHALL accept `max_critical`, `max_sox`, `max_gdpr`, `max_rbi` query parameters |

### 3.7 Dashboard

| ID | Requirement |
|----|-------------|
| FR-DB-01 | The system SHALL provide a Streamlit dashboard with multi-database estate overview |
| FR-DB-02 | The dashboard SHALL display per-database health scores, critical/high counts, and environment labels |
| FR-DB-03 | The dashboard SHALL display health score trend charts per database |
| FR-DB-04 | The dashboard SHALL display stacked severity bar charts and new-vs-resolved area charts |
| FR-DB-05 | The dashboard SHALL allow database selection via dropdown for trend detail views |
| FR-DB-06 | The dashboard SHALL provide a COMPLIANCE sidebar section with pages: Compliance Overview, SOX Findings, GDPR Findings, RBI Findings, Dangerous DML |
| FR-DB-07 | The Issues Explorer page SHALL display a highlighted banner when Dangerous DML findings (DNG001–DNG006) are present in the selected run |

### 3.8 Multi-Database Management

| ID | Requirement |
|----|-------------|
| FR-MD-01 | The system SHALL maintain a PostgreSQL registry of SQL Server databases (`db_registry`) |
| FR-MD-02 | The system SHALL sync the `databases:` YAML list into the registry via `dbanalyser db sync` |
| FR-MD-03 | The system SHALL support running analysis against all active databases with `--all-dbs` |
| FR-MD-04 | Databases SHALL be soft-deleteable (deactivated, not physically removed) |
| FR-MD-05 | The system SHALL support both Windows Authentication and SQL Server Authentication per database entry |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement |
|----|-------------|
| NFR-P-01 | Rule execution SHALL be parallelised with a default of 4 worker threads (configurable up to 32) |
| NFR-P-02 | Analysis of 500 SQL objects SHALL complete within 60 seconds on standard hardware |
| NFR-P-03 | Bulk finding inserts SHALL use a single multi-row INSERT statement (not per-row loops) |
| NFR-P-04 | Dashboard data calls SHALL be cached for 60 seconds to avoid repeated PostgreSQL queries |

### 4.2 Reliability

| ID | Requirement |
|----|-------------|
| NFR-R-01 | A single rule failure SHALL NOT abort the analysis of other objects or rules |
| NFR-R-02 | PostgreSQL connection failure at API startup SHALL be logged as a warning — the API SHALL still start |
| NFR-R-03 | File scan errors (unreadable files, encoding issues) SHALL be logged and skipped |

### 4.3 Security

| ID | Requirement |
|----|-------------|
| NFR-S-01 | Database passwords SHALL NOT be committed to version control |
| NFR-S-02 | All sensitive config values SHALL be overrideable via environment variables (prefix: `DBANALYSER_`) |
| NFR-S-03 | The REST API SHALL support API key protection for all data endpoints |
| NFR-S-04 | Connection strings stored in `db_registry` SHALL be treated as secrets |

### 4.4 Maintainability

| ID | Requirement |
|----|-------------|
| NFR-M-01 | Every rule class SHALL have at least one positive detection test and one no-false-positive test |
| NFR-M-02 | Test suite SHALL maintain 100% pass rate at 168 tests; zero warnings |
| NFR-M-03 | Adding a new rule SHALL require changes to at most 3 files: the rule module, `__init__.py`, and a test file |
| NFR-M-04 | All SQL SHALL be isolated in `db/repository.py` |

### 4.5 Configurability

| ID | Requirement |
|----|-------------|
| NFR-C-01 | All operational parameters SHALL be configurable via `analysis_config.yaml` |
| NFR-C-02 | Any YAML value SHALL be overrideable via environment variable `DBANALYSER_<SECTION>_<KEY>` |
| NFR-C-03 | Old YAML key names SHALL be supported via backward-compatible aliases in model validators |

---

## 5. System Architecture

### 5.1 Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     User Interfaces                      │
│   CLI (Click)    REST API (FastAPI)   Dashboard (Streamlit) │
└──────────┬──────────────┬────────────────────┬──────────┘
           │              │                    │
           ▼              ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│                    Core Engine                           │
│   config.py → Settings     engine/analyser.py           │
│   engine/scanner.py        engine/rules/*               │
│   engine/dmv.py            reports/*                    │
└──────────────────────────┬──────────────────────────────┘
                           │
           ┌───────────────┴──────────────┐
           ▼                              ▼
┌──────────────────┐           ┌──────────────────────┐
│  SQL Server      │           │  PostgreSQL           │
│  (source data)   │           │  db_registry          │
│  ODBC / files    │           │  runs                 │
└──────────────────┘           │  findings             │
                               │  health_trend         │
                               └──────────────────────┘
```

### 5.2 Data Flow

```
analysis_config.yaml
        │
        ▼
  load_config() → Settings
        │
        ▼
  load_objects(cfg) ──── SQL Server (live) or filesystem (file)
        │
        ▼ List[SQLObject]
  build_rule_set(cfg) → List[BaseRule]  (includes compliance packs)
        │
        ▼
  ThreadPoolExecutor → _run_rules_for_object() × N workers
        │
        ▼ List[ObjectResult]
  AnalysisResult (health score, severity counts, findings)
        │
    ┌───┴─────────────────────┐
    ▼                         ▼
generate_*()           insert_run()
(Excel/HTML/CSV/JSON)  bulk_insert_findings()
                       upsert_health_trend()
```

---

## 6. Data Requirements

### 6.1 PostgreSQL Schema

#### `db_registry`
Stores registered SQL Server databases.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | Internal integer identifier |
| name | TEXT UNIQUE | Friendly label (e.g. LTFS_PROD) |
| environment | TEXT | development / uat / production |
| host | TEXT | SQL Server hostname |
| port | INTEGER | Default 1433 |
| database_name | TEXT | SQL Server database name |
| connection_string | TEXT | Full DSN (overrides host/port/db) |
| use_windows_auth | BOOLEAN | True = Trusted Connection |
| username / password | TEXT | SQL Auth credentials |
| description / owner_label | TEXT | Metadata |
| tags | TEXT[] | Array of freeform labels |
| is_active | BOOLEAN | False = soft-deleted |
| last_run_at | TIMESTAMPTZ | Timestamp of most recent run |
| last_health | NUMERIC | Health score from most recent run |
| created_at / updated_at | TIMESTAMPTZ | Audit timestamps |

#### `runs`
One row per analysis execution.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | Integer FK used by findings and health_trend |
| run_id | TEXT UNIQUE | UUID string for human reference |
| label | TEXT | Human-readable run label |
| db_registry_id | BIGINT FK | References db_registry.id (nullable) |
| source_mode | TEXT | file / live_db |
| total_objects | INTEGER | Objects scanned |
| total_issues | INTEGER | Findings produced |
| critical_count / high_count / medium_count / low_count | INTEGER | Per-severity totals |
| health_score | NUMERIC | 0–100 |
| status | TEXT | success / failed |
| timestamp | TIMESTAMPTZ | Run start time |
| duration_sec | NUMERIC | Wall-clock elapsed seconds |

#### `findings`
One row per finding per object per run.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | |
| run_id | BIGINT FK | References runs.id (integer, NOT uuid) |
| schema_name | TEXT | SQL object schema |
| object_name | TEXT | SQL object name |
| object_type | TEXT | Stored Procedure / View / Table / Function / Trigger |
| rule_id | TEXT | e.g. SEC001, DNG003, SOX002 |
| category | TEXT | Security / Reliability / Compliance-SOX etc. |
| severity | TEXT | Critical / High / Medium / Low |
| issue | TEXT | Finding description |
| recommendation | TEXT | Remediation guidance |
| line_number | INTEGER | Source line of finding |
| snippet | TEXT | Surrounding source lines |
| status | TEXT | open / acknowledged / fixed / suppressed / wontfix |
| status_reason / jira_ticket | TEXT | Lifecycle metadata |
| is_new / is_regression | BOOLEAN | Diff flags |
| created_at / updated_at | TIMESTAMPTZ | Audit timestamps |

#### `health_trend`
One row per run per database — drives trend charts.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | |
| run_id | BIGINT UNIQUE FK | References runs.id |
| db_registry_id | BIGINT FK | References db_registry.id (nullable) |
| db_name / environment | TEXT | Denormalised for query efficiency |
| timestamp | TIMESTAMPTZ | Trend point time |
| health_score | NUMERIC | 0–100 |
| total_objects / total_issues | INTEGER | |
| critical_count / high_count / medium_count / low_count | INTEGER | |
| new_issues / resolved_issues | INTEGER | Diff vs previous run |

---

## 7. Interface Requirements

### 7.1 CLI Interface

Entry point: `dbanalyser` (registered via pyproject.toml `[project.scripts]`)

All commands accept `--config PATH` (default: `analysis_config.yaml`) and `--verbose / -v`.

### 7.2 REST API Interface

Base URL: `http://<host>:<port>` (default `http://localhost:8000`)

Authentication: Optional `X-API-Key: <value>` header or `?api_key=<value>` query parameter.

Content type: `application/json` for all endpoints except `/reports/download` (streamed file).

### 7.3 Configuration File Interface

Format: YAML. Schema validated by Pydantic v2 `Settings` model on load.
Environment variable overrides: `DBANALYSER_<SECTION>_<KEY>=value`

### 7.4 External System Interfaces

| System | Protocol | Purpose |
|--------|----------|---------|
| SQL Server | ODBC (pyodbc) | Live-DB source scanning |
| PostgreSQL | psycopg2 connection pool | Results persistence |
| File system | OS file I/O | File-mode SQL scanning and report output |
| Windows Task Scheduler | XML template in deployment/ | Optional OS-level scheduled runs |
| Slack | HTTPS POST (Incoming Webhook) | Alert notifications after analysis runs |
| Microsoft Teams | HTTPS POST (Incoming Webhook) | Alert notifications after analysis runs |
| Docker Engine | Dockerfile / docker-compose.yml | Containerised API + PostgreSQL deployment |

---

## 8. Rule Engine Specification

### 8.1 Base Contract (`engine/rules/base.py`)

```
BaseRule (ABC)
  rule_id:  str          — unique identifier e.g. "SEC001"
  category: str          — display category string
  enabled:  bool         — default True
  analyse(obj: SQLObject) -> List[RuleFinding]

SQLObject
  name, obj_type, schema, source, file_path
  source_upper, source_lines  — pre-computed

RuleFinding
  rule_id, category, severity, issue, recommendation
  line_number, snippet
```

### 8.2 Rule Categories and Counts

| Category | Rule File | IDs | Count |
|----------|-----------|-----|-------|
| Security | security.py | SEC001–005 | 5 |
| Reliability | reliability.py | REL001–004 | 4 |
| Performance | performance.py | PERF001–008 | 8 |
| Data Safety | data_safety.py | DS001–006 | 6 |
| Best Practices | best_practices.py | BP001–005 | 5 |
| Parameter Sniffing | parameter_sniffing.py | PS001–004 | 4 |
| Maintainability | maintainability.py | MNT001–006 | 6 |
| Data Safety / Reliability | dangerous_sql.py | DNG001–006 | 6 |
| **Base total** | | | **44** |

### 8.3 Rule Selection Logic

```python
# analyser.py
effective_rules = build_rule_set(cfg)
# = ALL_RULES (44) + compliance packs if enabled_packs is non-empty
```

---

## 9. Compliance Pack Specification

### 9.1 SOX (Sarbanes-Oxley) — sox.py

| Rule ID | What it detects | Severity |
|---------|-----------------|----------|
| SOX001 | Financial table missing audit-trail columns (CreatedBy, ModifiedBy, dates) | High |
| SOX002 | Financial SP/trigger performs DML without writing to an audit/log table | High |
| SOX003 | xp_cmdshell or linked server used inside a financial object | Critical / High |
| SOX004 | GRANT permission on a financial table | High |
| SOX005 | Financial procedure has transaction but no TRY/CATCH | High |
| SOX006 | Hardcoded tax rate / interest rate / commission constant | Medium |

Financial object detection: keyword match on `account|ledger|journal|transaction|payment|invoice|revenue|expense|balance|financial|audit|payroll|budget|forecast|remittance` (no word-boundary restriction — matches CamelCase names).

### 9.2 GDPR — gdpr.py

| Rule ID | What it detects | Severity |
|---------|-----------------|----------|
| GDPR001 | SELECT * on an object referencing PII columns | High |
| GDPR002 | PII column referenced inside PRINT / RAISERROR / THROW | High |
| GDPR003 | View or SP returns PII columns without masking or encryption | High |
| GDPR004 | Hardcoded email address or phone number literal in code | Medium |
| GDPR005 | Table with PII columns has no retention or expiry hint | Medium |
| GDPR006 | SP inserts personal data without referencing consent status | Medium |

PII patterns: `email|phone|mobile|ssn|nric|dob|passport|address|credit_card` (configurable via `compliance.pii_column_patterns`).

### 9.3 RBI (Reserve Bank of India) — rbi.py

| Rule ID | What it detects | Severity |
|---------|-----------------|----------|
| RBI001 | Financial table stores sensitive columns (account_no, card_no, PIN) without encryption | Critical |
| RBI002 | Financial SP/trigger modifies data without writing to an audit log | Critical |
| RBI003 | View on financial table exposes data without row-level filtering | High |
| RBI004 | Financial table definition has no Row-Level Security policy reference | Medium |
| RBI005 | Financial SP has transactions but lacks TRY/CATCH + ROLLBACK | High |
| RBI006 | Hardcoded connection string in a financial object | High |

Financial object detection: keyword match on `account|transaction|txn|transfer|remittance|payment|loan|deposit|withdrawal|ledger|neft|rtgs|imps|upi|kyc|aml|emi|balance|credit|debit` (no word-boundary restriction).

### 9.4 Activating Compliance Packs

In `analysis_config.yaml`:
```yaml
compliance:
  enabled_packs: [sox, gdpr, rbi]   # any combination
```

---

## 10. Constraints and Assumptions

### 10.1 Constraints
- C-01: Source SQL files must be UTF-8 or UTF-8-BOM encoded
- C-02: Live-DB mode requires Microsoft ODBC Driver 17 (or 18) installed on the host
- C-03: PostgreSQL persistence requires PostgreSQL 13 or higher
- C-04: The REST API background job registry (`_JOBS` dict) is in-process only — not suitable for multi-worker deployments without a persistent job store (Phase B)
- C-05: Dashboard requires network access to PostgreSQL from the Streamlit host
- C-06: The built-in scheduler requires the API server to be running — it operates as a background thread within the API process
- C-07: JWT secret key MUST be changed from the default before production deployment

### 10.2 Assumptions
- A-01: SQL Server objects are accessible via Windows Authentication or SQL Server Authentication
- A-02: The PostgreSQL database named `dbanalyser` exists prior to running `init-db`
- A-03: Users running `--all-dbs` have credentials for all active registered databases
- A-04: The compliance pack keyword lists are sufficient for LTFS's naming conventions; additional keywords can be added via `ComplianceConfig` overrides

### 10.3 Future Extensions (Out of Scope for current release)
- Multi-worker API with Redis job queue
- SAML / OAuth2 SSO integration
- Rule marketplace / shared rule registry

---

## 11. Phase C & D Functional Requirements

### FR-CR: Custom Rules (YAML-driven)

| ID | Requirement |
|----|-------------|
| FR-CR-01 | The system SHALL load custom rule definitions from YAML files in a configured directory |
| FR-CR-02 | Each YAML rule SHALL specify: id, name, category, severity, description, recommendation, patterns |
| FR-CR-03 | Custom rules SHALL support an `applies_to` list to restrict execution to specific object types |
| FR-CR-04 | Custom rule patterns SHALL be Python regular expressions matched case-insensitively against uppercased SQL source |
| FR-CR-05 | Custom rules SHALL be merged with built-in rules in `build_rule_set()` when `custom_rules.enabled: true` |
| FR-CR-06 | Duplicate custom rule IDs SHALL raise a validation error at startup |
| FR-CR-07 | YAML syntax errors in rule files SHALL produce informative error messages and abort startup |
| FR-CR-08 | Individual rules within a file MAY be disabled via `enabled: false` without removing the file |

### FR-NT: Notifications (Webhook Alerts)

| ID | Requirement |
|----|-------------|
| FR-NT-01 | The system SHALL POST a JSON summary to a configured Slack Incoming Webhook URL after each analysis run |
| FR-NT-02 | The system SHALL POST an Adaptive Card payload to a configured Microsoft Teams webhook URL after each analysis run |
| FR-NT-03 | Notifications SHALL only fire when `notifications.enabled: true` |
| FR-NT-04 | Notifications SHALL only fire when the count of findings matching `alert_on_severity` is ≥ `min_findings_to_alert` |
| FR-NT-05 | HTTP errors or connection failures during webhook delivery SHALL be logged as warnings and SHALL NOT interrupt or fail the analysis run |
| FR-NT-06 | The notification payload SHALL include: database name, run label, health score, per-severity counts |
| FR-NT-07 | Both Slack and Teams webhooks MAY be active simultaneously; each fires independently |

### FR-SC: Scheduled Scans

| ID | Requirement |
|----|-------------|
| FR-SC-07 | The system SHALL maintain a `scheduled_tasks` table in PostgreSQL for persistent task storage |
| FR-SC-08 | Each scheduled task SHALL have a name, 5-field cron expression, target database, and active flag |
| FR-SC-09 | The scheduler SHALL run as a background thread within the API process, polling every `scheduler.check_interval_sec` seconds |
| FR-SC-10 | The scheduler SHALL execute all tasks whose `next_run_at` is in the past and `is_active = true` |
| FR-SC-11 | After firing, the scheduler SHALL update `last_run_at` and advance `next_run_at` to the next cron occurrence |
| FR-SC-12 | The CLI SHALL support `schedule list`, `schedule add`, `schedule remove`, and `schedule run-due` sub-commands |
| FR-SC-13 | The scheduler SHALL be skipped entirely when `scheduler.enabled: false` |

### FR-AU: Authentication (JWT RBAC)

| ID | Requirement |
|----|-------------|
| FR-AU-01 | When `auth.enabled: true`, the API SHALL require a valid JWT Bearer token on all protected endpoints |
| FR-AU-02 | Tokens SHALL be issued via `POST /auth/token` accepting `username` and `password` as form fields |
| FR-AU-03 | Passwords SHALL be stored as bcrypt hashes in `auth.users` config; never as plaintext |
| FR-AU-04 | `GET /auth/me` SHALL return the authenticated user's username and roles |
| FR-AU-05 | The `dbanalyser auth hash-password` CLI command SHALL interactively hash a plaintext password using bcrypt |
| FR-AU-06 | Tokens SHALL expire after `auth.token_expire_minutes` (default 480 minutes) |
| FR-AU-07 | Supported roles SHALL be `admin` (full access) and `viewer` (read-only endpoints) |
| FR-AU-08 | JWT auth and static API key auth SHALL be independently configurable and MAY coexist |

### FR-DO: Docker Deployment

| ID | Requirement |
|----|-------------|
| FR-DO-01 | A `Dockerfile` SHALL be provided that builds a self-contained image running the API server |
| FR-DO-02 | A `docker-compose.yml` SHALL be provided that starts the API service and a PostgreSQL service together |
| FR-DO-03 | All sensitive configuration values (passwords, secret keys, API keys) SHALL be injectable via environment variables in the Docker environment |
| FR-DO-04 | The container SHALL expose port 8000 for the API server |
| FR-DO-05 | `dbanalyser init-db` SHALL be runnable inside the container via `docker compose exec` to initialise the schema |

### Updated schema tables (Phase C/D additions)

#### `scheduled_tasks`
Stores persistent scheduled scan tasks managed by `dbanalyser schedule`.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | |
| name | TEXT UNIQUE | Human-readable task name |
| cron_expression | TEXT | 5-field cron string (UTC) |
| db_name | TEXT | Target database name or `all` |
| label_template | TEXT | Label applied to triggered runs |
| is_active | BOOLEAN | False = paused |
| last_run_at | TIMESTAMPTZ | Timestamp of last execution |
| next_run_at | TIMESTAMPTZ | Pre-computed next fire time |
| created_at | TIMESTAMPTZ | Audit timestamp |

#### `jobs`
Persists async API-triggered and scheduler-triggered analysis jobs.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | UUID job identifier |
| status | TEXT | queued / running / done / failed |
| db_name | TEXT | Target database |
| label | TEXT | Run label |
| run_id | BIGINT FK | References runs.id once complete |
| error | TEXT | Error message if failed |
| created_at / updated_at | TIMESTAMPTZ | Audit timestamps |

### Updated test count

| Phase | Test files | Tests |
|-------|-----------|-------|
| A/B (original) | test_rules.py, test_dangerous_sql.py, test_compliance.py, test_scanner.py | 112 |
| C/D (new) | test_custom_rules.py, test_webhooks.py, test_scheduler.py | 56 |
| **Total** | **7 files** | **168** |

### Updated NFR-M-02

```
NFR-M-02: Test suite SHALL maintain 100% pass rate at 168 tests; zero warnings
```
