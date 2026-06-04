# DBAnalyser — User Manual
## Version 2.0.0 | LTFS Technology | March 2026

---

## Table of Contents

1. Getting Started
2. Running Your First Analysis
3. Understanding Results
4. CLI Command Reference
5. Report Formats
6. REST API Quick Start
7. Dashboard Guide
8. Compliance Packs
9. Multi-Database (Estate) Mode
10. CI/CD Integration
11. Finding Lifecycle Management
12. Tips and Best Practices
13. Compliance Report Command
14. Schedule Commands
15. Auth Commands
16. Compliance Dashboard Pages
17. Webhook Notification Setup

---

## 1. Getting Started

### 1.1 What DBAnalyser does

DBAnalyser scans your SQL Server code (stored procedures, views, tables, functions, triggers)
and tells you:

- **Security risks** — SQL injection vectors, hardcoded credentials, xp_cmdshell usage
- **Reliability issues** — missing error handling, transactions without rollback
- **Performance problems** — SELECT *, NOLOCK hints, cursors, non-sargable WHERE clauses
- **Data safety concerns** — UPDATE/DELETE without WHERE, implicit NULL comparisons
- **Compliance violations** — SOX audit trail gaps, GDPR PII exposure, RBI encryption requirements
- **Maintainability debt** — overly long procedures, deep nesting, magic numbers

Each finding comes with a **severity** (Critical / High / Medium / Low), a clear **issue description**, and an actionable **recommendation**.

### 1.2 Quick install check

```bash
dbanalyser --version
# DBAnalyser, version 2.0.0
```

If the command is not found, ensure the virtual environment is activated:
```bash
D:\LTFS\ltfs-analyzer\.venv\Scripts\activate
```

---

## 2. Running Your First Analysis

### 2.1 Analyse SQL files on disk

```bash
dbanalyser run
```

This reads `analysis_config.yaml` from the current directory, scans the path in
`source.file_path`, and writes reports to `./output/`.

### 2.2 Analyse with a custom config

```bash
dbanalyser run --config path\to\my_config.yaml
```

### 2.3 Analyse a specific registered database (live)

```bash
dbanalyser run --db-name LTFS_DEV
```

### 2.4 Analyse all registered databases at once

```bash
dbanalyser run --all-dbs
```

### 2.5 Label your run

```bash
dbanalyser run --label "sprint-42-release"
```

### 2.6 Choose output format

```bash
dbanalyser run --format excel     # Excel only (.xlsx)
dbanalyser run --format html      # HTML only
dbanalyser run --format csv       # CSV only
dbanalyser run --format json      # JSON only
dbanalyser run --format all       # All formats (default)
```

### 2.7 Run without saving to PostgreSQL

```bash
dbanalyser run --no-persist
```

Useful for quick local checks when PostgreSQL is not available.

---

## 3. Understanding Results

### 3.1 Severity levels

| Severity | Meaning | Recommended action |
|----------|---------|-------------------|
| **Critical** | Security exploit, data loss risk, OS access | Fix immediately before any deployment |
| **High** | Correctness or integrity bug, compliance breach | Fix in current sprint |
| **Medium** | Performance problem, bad pattern | Plan fix within 2 sprints |
| **Low** | Style, minor improvement | Address during refactoring |

### 3.2 Health score

The health score is a 0–100 number calculated as:

```
Health = 100 - (Critical × 5) - (High × 2) - (Medium × 0.5) - (Low × 0.1)
Minimum: 0
```

| Score | Meaning |
|-------|---------|
| 85–100 | Good — minor issues only |
| 70–84 | Acceptable — high-priority items need attention |
| 50–69 | Concerning — significant technical debt |
| < 50 | Critical — immediate action required |

### 3.3 Terminal output

After a run you will see a summary table:

```
                    ✓ 20260330_143022
  Metric       Value
  Objects      142
  Findings     38
  Critical     2
  High         8
  Medium       18
  Low          10
  Health       76.5
  Elapsed      3.4s
```

### 3.4 Output files

All reports are written to `./output/` by default (configurable via `output.directory`):

```
output/
  dbanalyser_20260330_143022.xlsx
  dbanalyser_20260330_143022.html
  dbanalyser_20260330_143022_findings.csv
  dbanalyser_20260330_143022.json
```

---

## 4. CLI Command Reference

### `dbanalyser run` — Run analysis

```
dbanalyser run [OPTIONS]

Options:
  --config / -c PATH      Path to config file (default: analysis_config.yaml)
  --label / -l TEXT       Human-readable label for this run
  --output-dir / -o PATH  Output directory for reports (default: ./output)
  --format / -f CHOICE    all | excel | html | csv | json  (default: all)
  --no-persist            Skip writing results to PostgreSQL
  --dmv                   Run live-DB DMV performance checks (requires live_db mode)
  --db-name TEXT          Run against one named registered database
  --all-dbs               Run against all active databases in the registry
```

### `dbanalyser report` — Generate report from stored run

```
dbanalyser report [OPTIONS]

Options:
  --run-id INTEGER        Integer run ID (default: latest)
  --db-name TEXT          Use latest run for this database
  --output-dir / -o PATH  Output directory
  --format / -f CHOICE    excel | html | csv | json  (default: excel)
```

### `dbanalyser history` — List previous runs

```
dbanalyser history [OPTIONS]

Options:
  --limit INTEGER         Number of runs to show (default: 20)
  --db-name TEXT          Filter to a specific database
```

### `dbanalyser diff` — Compare two runs

```
dbanalyser diff RUN_ID_A RUN_ID_B

Shows:
  + New findings (appeared in B, absent in A)
  - Resolved findings (present in A, absent in B)
  = Unchanged findings
```

### `dbanalyser api` — Start React UI backend

The primary UI is the React application at `dbanalyser-ui/`. Start its backend with:
```bash
dbanalyser api --port 8000
```
Then open the React UI at `http://localhost:5173` (run `npm run dev` inside `dbanalyser-ui/`).

### `dbanalyser dashboard` — Launch legacy Streamlit dashboard (deprecated)

```
dbanalyser dashboard [OPTIONS]

Options:
  --port INTEGER          Port for Streamlit (default: 8501)
  --no-browser            Don't open browser automatically
```

> **Deprecated**: The Streamlit dashboard is superseded by the React UI. Use `dbanalyser api` + the React frontend instead.

### `dbanalyser validate` — Test connections

```
dbanalyser validate [OPTIONS]

Options:
  --db-name TEXT          Validate one specific database

Tests: SQL Server connection(s) + PostgreSQL connection
```

### `dbanalyser api` — Start REST API server

```
dbanalyser api [OPTIONS]

Options:
  --host TEXT             Bind host (default: 0.0.0.0)
  --port INTEGER          TCP port (default: 8000)
  --reload                Auto-reload on code changes (dev only)
  --api-key TEXT          API authentication key (env: DBANALYSER_API_API_KEY)
```

### `dbanalyser db` — Database registry commands

```
dbanalyser db list [--all]              List all registered databases
dbanalyser db add NAME [OPTIONS]        Add or update a database
dbanalyser db remove NAME               Deactivate a database
dbanalyser db show NAME                 Show details and last 5 runs
dbanalyser db sync                      Push config databases into PostgreSQL
```

### `dbanalyser init-db` — Create PostgreSQL schema

```
dbanalyser init-db
```

Run once after initial installation, or after a schema upgrade.

### `dbanalyser compliance-report` — Generate compliance-only report

```
dbanalyser compliance-report [OPTIONS]

Options:
  --run-id INTEGER        Integer run ID (default: latest)
  --db-name TEXT          Use latest run for this database
  --packs TEXT            Comma-separated compliance packs to include (default: all enabled)
                          e.g. --packs sox,gdpr
  --output-dir / -o PATH  Output directory (default: ./output)
  --format / -f CHOICE    excel | json | csv  (default: excel)
```

Generates a report containing **only compliance findings** (SOX, GDPR, RBI categories). All non-compliance findings are excluded. Use this command to produce the artifact for a compliance audit.

**Examples:**

```bash
# Generate Excel compliance report from the latest run
dbanalyser compliance-report

# Generate for a specific run in all three formats
dbanalyser compliance-report --run-id 42 --format excel
dbanalyser compliance-report --run-id 42 --format json
dbanalyser compliance-report --run-id 42 --format csv

# Only include SOX and GDPR findings
dbanalyser compliance-report --packs sox,gdpr --output-dir ./compliance_artifacts

# Use the latest run for a specific database
dbanalyser compliance-report --db-name LTFS_PROD --format excel
```

### `dbanalyser schedule` — Manage scheduled scan tasks

```
dbanalyser schedule list                        List all scheduled tasks
dbanalyser schedule add [OPTIONS]               Add a new scheduled task
dbanalyser schedule remove --name TEXT          Remove a task by name
dbanalyser schedule run-due                     Manually execute all tasks currently due
```

`schedule add` options:

```
  --name TEXT             Task name (required)
  --cron TEXT             5-field cron expression e.g. "0 2 * * *"  (required)
  --db-name TEXT          Target database name, or "all" for all active databases
  --label TEXT            Label template applied to triggered runs
  --active / --no-active  Activate immediately (default: active)
```

**Examples:**

```bash
# List all tasks
dbanalyser schedule list

# Schedule a nightly full-estate run at 02:00 UTC
dbanalyser schedule add \
  --name "nightly-all" \
  --cron "0 2 * * *" \
  --db-name all \
  --label "nightly"

# Schedule a weekly SOX scan on Monday at 06:00
dbanalyser schedule add \
  --name "weekly-sox" \
  --cron "0 6 * * 1" \
  --db-name LTFS_PROD \
  --label "weekly_sox"

# Remove a task
dbanalyser schedule remove --name "weekly-sox"

# Fire all overdue tasks immediately (useful for testing)
dbanalyser schedule run-due
```

### `dbanalyser auth` — Authentication commands

```
dbanalyser auth hash-password     Interactively hash a plaintext password (bcrypt)
```

**Example:**

```bash
dbanalyser auth hash-password
# Password: ************
# Confirm:  ************
# Hashed password: $2b$12$...
```

Copy the printed hash into `analysis_config.yaml` under `auth.users[].hashed_password`.
For full JWT auth setup see the Admin Manual, section 15.

---

## 5. Report Formats

### 5.1 Excel (.xlsx)

Two sheets:
- **Findings** — one row per finding, with columns: schema, object, type, rule_id, category, severity, issue, recommendation, line_number, snippet
- **Summary** — run metadata: label, health score, total objects, total findings, per-severity counts

### 5.2 HTML

A self-contained HTML file with:
- Run header (label, timestamp, health score)
- Colour-coded findings table (red = Critical, orange = High, yellow = Medium, green = Low)
- Sortable columns

### 5.3 CSV

A flat CSV of all findings — suitable for importing into Excel, Power BI, or JIRA bulk import.

### 5.4 JSON

```json
{
  "run": {
    "label": "sprint-42",
    "health_score": "76.5",
    "total_issues": "38"
  },
  "findings": [
    {
      "rule_id": "SEC001",
      "category": "Security",
      "severity": "Critical",
      "object_name": "usp_GetCustomer",
      "issue": "Potential SQL injection...",
      "recommendation": "Use sp_executesql...",
      "line_number": 14
    }
  ]
}
```

---

## 6. REST API Quick Start

### 6.1 Start the API

```bash
dbanalyser api --port 8000
```

### 6.2 Explore the API

Open in browser: `http://localhost:8000/docs`

The Swagger UI lists all endpoints with request/response schemas. Click **Try it out** on any endpoint.

### 6.3 Common API calls

**Check server health:**
```bash
curl http://localhost:8000/health
```

**List all databases:**
```bash
curl -H "X-API-Key: your-key" http://localhost:8000/databases
```

**List recent runs:**
```bash
curl -H "X-API-Key: your-key" http://localhost:8000/runs?limit=10
```

**Get findings for a run:**
```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/findings/run/42?severity=Critical"
```

**Trigger a new analysis run:**
```bash
curl -X POST -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"db_name": "LTFS_DEV", "label": "api-triggered-run"}' \
  http://localhost:8000/runs/trigger
```

Response:
```json
{"job_id": "a3f8c2e1-...", "status": "queued", "message": "Analysis job queued."}
```

**Poll job status:**
```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/runs/jobs/a3f8c2e1-...
```

**Download Excel report:**
```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/reports/download/42?fmt=excel" \
  -o report_run42.xlsx
```

---

## 7. React UI Dashboard Guide

### 7.1 Start the API and open the UI

**Step 1 — Start the FastAPI backend:**
```bash
# Activate virtual environment first
.venv\Scripts\activate          # Windows
python3 -m dbanalyser api --port 8000
# API running at http://localhost:8000
```

**Step 2 — Start the React frontend (development):**
```bash
cd dbanalyser-ui
npm run dev
# UI running at http://localhost:5173
```

**Step 3 — Open in browser:**
Navigate to `http://localhost:5173`

> **Auth disabled mode**: If `auth.enabled: false` in `analysis_config.yaml`, the UI logs in automatically as `anonymous` with admin rights. No username or password is needed.

---

### 7.2 Top bar controls

| Control | Description |
|---------|-------------|
| **Database selector** | Drop-down of all registered databases. Selecting one filters the Run selector. |
| **Run selector** | Drop-down of analysis runs for the selected database. Choosing a run loads findings across all pages. |
| **User indicator** | Shows logged-in username. Displays a Logout button when auth is enabled. |

---

### 7.3 Left sidebar navigation

| Icon | Page | Description |
|------|------|-------------|
| `dashboard` | **Dashboard** | Estate overview — health scores, KPI cards, run history |
| `analytics` | **Analysis** | Findings explorer, charts by category and severity |
| `schema` | **Schema Quality** | Tables without PK, index issues, column types |
| `shield` | **Compliance** | SOX, GDPR, RBI, Security, Dangerous SQL findings |
| `download` | **Reports** | Download reports, health gate, trend analysis, audit log |
| `monitor_heart` | **Live DB** | Live DMV performance findings, trigger new live scan |
| `manage_accounts` | **Administration** | Database registry, schedules, users, system info |

---

### 7.4 Dashboard page

**Estate Overview tab:**
- KPI cards: number of databases, overall health, total findings, critical issues, last run date
- **Health Score by Database** bar chart — per database, colour-coded green/amber/red
- **Findings by Severity** donut chart — Critical / High / Medium / Low
- Database cards grid with health bar and host:port info

**Database Detail tab:** Select a database from the top bar for detailed metrics.

**Trend Analysis tab:** Health score bar chart across the last 10 runs.

**Run History tab:** Table of all runs with date, health score, and findings count.

---

### 7.5 Analysis page

**Overview tab:** KPI row (Total Findings, Critical, High, Medium, Low) + Findings by Category bar chart + By Severity donut chart.

**Issues Explorer tab:**
- Search box (full-text across all fields)
- Severity and Category drop-down filters
- Findings table: Severity badge · Category · Object · Rule · Issue
- Shows up to 100 rows with a count banner when truncated

**By Category tab:** Cards showing each category's finding count and percentage of total.

**Risk Scoreboard tab:** Top 20 objects ranked by total findings, with Critical and High columns highlighted.

---

### 7.6 Schema Quality page

**Overview tab:** KPI cards (total objects, tables without PK, duplicate indexes, missing FKs) + Object type distribution.

**Tables Without PK tab:** List of tables that have no primary key defined.

**Index Issues tab:** Tables with duplicate or missing covering indexes.

**Column Types tab:** Columns using TEXT/NTEXT, implicit NULLable columns, and oversized NVARCHAR.

**Orphan & Unused tab:** Views and procedures that are not referenced anywhere in the codebase.

---

### 7.7 Compliance page

**Overview tab:** KPI cards (total compliance findings per framework) + Findings by Category bar chart + severity breakdown donut.

**SOX tab:** Sarbanes-Oxley findings — audit trail gaps, financial data integrity issues.

**GDPR tab:** PII exposure, unmasked personal data columns.

**RBI tab:** Reserve Bank of India mandates — encryption, transaction audit.

**Security tab:** Hardcoded credentials, SQL injection vectors, xp_cmdshell usage.

**Dangerous SQL tab:** DELETE / TRUNCATE without WHERE, DROP statements.

All compliance finding rows are expandable — click a row to see the full **Issue**, **Recommendation**, and **Code Snippet**.

---

### 7.8 Reports page

**Download Report tab:**
- Select report format: Excel, HTML, JSON, CSV
- Click **Download** to fetch the report for the currently selected run
- Available Runs panel shows recent runs with a per-run quick-download button

**Health Gate tab:** Pass/Fail gate result for the selected run showing threshold vs actual score.

**Trend Analysis tab:** Multi-database health score line chart over time.

**Audit Log tab:** Last 50 system events (runs triggered, users changed, databases added/removed).

> **Note**: The Excel report format currently returns HTTP 500 from the backend. Use JSON, HTML, or CSV until the backend Excel writer is fixed.

---

### 7.9 Live DB page

**Overview tab:** KPI cards from the most recent live-scan run + finding count by category.

**Performance tab:** Performance findings (SELECT *, non-sargable WHERE, missing indexes) from live runs.

**Index Analysis tab:** Index-related findings from live DMV checks.

**Data Safety tab:** Safety findings (NULL comparison errors, division-by-zero, string truncation).

**Run Live Scan tab:** Trigger a new live-DB analysis:
1. Select a database from the drop-down
2. Click **Trigger Live Scan**
3. The run is queued via `POST /runs/trigger` and results appear after completion

---

### 7.10 Administration page

**Databases tab:** Register new databases (host, port, name, environment, credentials) and remove existing ones.

**Schedules tab:** Create and manage scheduled scan tasks:
- Schedules are stored in browser localStorage
- Built-in CRON presets (daily midnight, weekly Monday, every 6 hours, etc.)
- **Trigger Now** button executes the scan immediately

**Users & Org tab:** Invite new users (requires auth enabled) and change your own password.

**System tab:** Displays API version, database record counts, and Python/FastAPI version info.

---

## 8. Compliance Packs

### 8.1 What they are

Compliance packs are additional rule sets that detect violations of specific regulatory frameworks. They are disabled by default and must be explicitly enabled.

| Pack | Framework | Rules | Key focus areas |
|------|-----------|-------|----------------|
| `sox` | Sarbanes-Oxley | SOX001–006 | Audit trails, financial data integrity, access controls |
| `gdpr` | General Data Protection Regulation | GDPR001–006 | PII exposure, data minimisation, retention |
| `rbi` | Reserve Bank of India IT Framework | RBI001–006 | Encryption, transaction audit, RLS |

### 8.2 Enable compliance packs

In `analysis_config.yaml`:

```yaml
compliance:
  enabled_packs: [sox, gdpr]     # enable SOX and GDPR
```

Or run a one-off scan with compliance enabled by creating a separate config file.

### 8.3 SOX findings explained

| Rule | What it flags | How to fix |
|------|---------------|-----------|
| SOX001 | Financial table missing CreatedBy / ModifiedBy / date columns | Add audit columns with DEFAULT constraints |
| SOX002 | DML on financial table without audit log insert | Add INSERT INTO <TableName>_Audit after each DML |
| SOX003 | xp_cmdshell or linked server in financial code | Remove — use SQL Agent or application layer |
| SOX004 | GRANT on financial table | Revoke direct grants; use stored procedures only |
| SOX005 | Transaction without TRY/CATCH | Wrap in BEGIN TRY / BEGIN CATCH with ROLLBACK |
| SOX006 | Hardcoded tax rate or commission | Move to a configuration or reference table |

### 8.4 GDPR findings explained

| Rule | What it flags | How to fix |
|------|---------------|-----------|
| GDPR001 | SELECT * on object referencing PII columns | Specify only needed columns |
| GDPR002 | PII column in PRINT / RAISERROR | Use anonymised IDs in error messages |
| GDPR003 | View returns PII without masking | Apply DDM or explicit masking (STUFF, HASHBYTES) |
| GDPR004 | Hardcoded email or phone literal | Remove — use parameterised queries |
| GDPR005 | PII table with no retention hint | Add a comment: `-- GDPR: retain N years, purge via sp_X` |
| GDPR006 | INSERT of personal data without consent check | Check consent flag before inserting |

### 8.5 RBI findings explained

| Rule | What it flags | How to fix |
|------|---------------|-----------|
| RBI001 | Sensitive columns (account_no, PIN) stored unencrypted | Apply ENCRYPTBYKEY or Always Encrypted |
| RBI002 | Financial DML without audit log | Insert into <Table>_Audit after every DML |
| RBI003 | View on financial table without row filter | Add WHERE clause or implement RLS |
| RBI004 | Financial table with no RLS policy reference | Create a Security Policy with filter predicate |
| RBI005 | Financial SP missing TRY/CATCH + ROLLBACK | Add full error-handling block |
| RBI006 | Hardcoded connection string in financial code | Move to Key Vault or encrypted configuration |

---

## 9. Multi-Database (Estate) Mode

### 9.1 Register your databases

Add entries to `analysis_config.yaml`:

```yaml
databases:
  - name: LTFS_DEV
    environment: development
    host: localhost
    port: 1433
    database_name: LTFS_Dev
    use_windows_auth: true
    owner_label: "DBA Team"
    tags: [dev]
    is_active: true

  - name: LTFS_PROD
    environment: production
    host: prod-sql-server
    port: 1433
    database_name: LTFS_Production
    use_windows_auth: true
    owner_label: "DBA Team"
    tags: [prod, critical]
    is_active: true
```

Then sync to PostgreSQL:
```bash
dbanalyser db sync
```

### 9.2 Run across all databases

```bash
dbanalyser run --all-dbs --label "nightly_$(date +%Y%m%d)"
```

You will see a per-database progress output, then a consolidated summary table:

```
╭──────────────┬─────────────┬────────┬──────────┬──────┬────────╮
│ Database     │ Env         │ Health │ Critical │ High │  Total │
├──────────────┼─────────────┼────────┼──────────┼──────┼────────┤
│ LTFS_DEV     │ development │   82.0 │        0 │    3 │     18 │
│ LTFS_UAT     │ uat         │   74.5 │        1 │    5 │     26 │
│ LTFS_PROD    │ production  │   91.0 │        0 │    1 │      9 │
╰──────────────┴─────────────┴────────┴──────────┴──────┴────────╘
```

---

## 10. CI/CD Integration

### 10.1 Health gate endpoint

Use `GET /reports/health-gate/{run_id}` to block deployments when quality thresholds are breached.

**Compliance-specific gate** (Phase C) — `GET /runs/{run_id}/health-gate`:

```bash
# Block if any Critical findings, any SOX violations, or more than 2 GDPR violations
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/runs/$RUN_ID/health-gate?max_critical=0&max_sox=0&max_gdpr=2"
```

Parameters: `max_critical`, `max_sox`, `max_gdpr`, `max_rbi` — all default to unlimited when omitted.

Use `GET /reports/health-gate/{run_id}` to block deployments when quality thresholds are breached.

```bash
# Returns HTTP 200 if thresholds pass, HTTP 422 if they fail
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/reports/health-gate/$RUN_ID?min_health=70&max_critical=0&max_high=5"
```

Response on pass:
```json
{"gate": "PASSED", "health": 82.0, "critical": 0, "high": 3}
```

Response on fail (HTTP 422):
```json
{
  "gate": "FAILED",
  "reasons": ["Health 65.0 < threshold 70", "Critical 2 > max 0"],
  "health": 65.0,
  "critical": 2,
  "high": 7
}
```

### 10.2 Azure DevOps / GitHub Actions pattern

```yaml
# In your pipeline YAML
- script: |
    dbanalyser run --db-name $(DB_NAME) --label "$(Build.BuildNumber)" --no-persist
    RUN_ID=$(curl -s -H "X-API-Key: $(API_KEY)" \
      http://localhost:8000/runs?limit=1 | python -c "import sys,json; print(json.load(sys.stdin)['runs'][0]['id'])")
    curl -sf -H "X-API-Key: $(API_KEY)" \
      "http://localhost:8000/reports/health-gate/$RUN_ID?min_health=70&max_critical=0"
  displayName: 'DBAnalyser Quality Gate'
  failOnStderr: false
```

### 10.3 Summary of findings severity for CI

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/findings/summary/$RUN_ID"
```

```json
{"run_id": 42, "critical": 0, "high": 3, "medium": 12, "low": 5, "total": 20}
```

---

## 11. Finding Lifecycle Management

### 11.1 Finding statuses

| Status | Meaning |
|--------|---------|
| `open` | Default — needs attention |
| `acknowledged` | Seen, will fix in future sprint |
| `fixed` | Remediated |
| `suppressed` | False positive — excluded from counts |
| `wontfix` | Accepted risk — documented decision |

### 11.2 Update via REST API

```bash
curl -X PATCH \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"status": "acknowledged", "reason": "Planned for Q3 refactor", "jira": "DB-1234"}' \
  http://localhost:8000/findings/123/status
```

### 11.3 Filter findings by status

```bash
# Get only open findings for a run
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/findings/run/42?status=open"
```

---

## 12. Tips and Best Practices

### Run a baseline first
Before enabling compliance packs, run a baseline scan (`--no-persist` is fine) so you understand the starting state of each database.

### Use labels consistently
Label runs with sprint numbers or dates: `--label "sprint-44"`. This makes the `diff` command and trend charts meaningful.

### Address Critical findings before High
The health score penalises Critical findings 2.5× more than High. One Critical finding costs as much as 2.5 High findings.

### Use the diff command for sprint reviews
```bash
dbanalyser diff 38 42
# Shows exactly what improved or regressed between two runs
```

### Set XACT_ABORT ON in all procedures that use transactions
This is the most common DNG003 finding. Add it as a template in your procedure header:
```sql
CREATE OR ALTER PROCEDURE dbo.usp_MyProc AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRY
        ...
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END
```

### Suppress low-noise findings systematically
Rather than disabling entire categories, use the `suppressed` status on individual findings you have accepted. This keeps the rule active for new code while ignoring known false positives.

### For GDPR compliance: name your columns clearly
The GDPR rules detect PII by column name patterns (`email`, `phone`, `ssn`, `dob` etc.). Using consistent, meaningful column names both satisfies the rule engine and documents the data model for compliance officers.

### Export to Excel for JIRA bulk import
The Excel report's Findings sheet maps cleanly to JIRA's CSV import format. Add columns `Project`, `Issue Type`, and `Priority` to the exported CSV for a clean one-step JIRA import.

---

## 13. Compliance Report Command

### 13.1 Overview

`dbanalyser compliance-report` generates a report containing **only compliance findings** (SOX / GDPR / RBI). It reads from an existing run stored in PostgreSQL — it does not re-run the analysis.

### 13.2 Common workflows

**Quarterly SOX audit export:**

```bash
dbanalyser run --all-dbs --label "Q1-2026-SOX" --config sox_only.yaml
dbanalyser compliance-report --packs sox --format excel --output-dir ./sox_audit/
```

**GDPR review for a specific database:**

```bash
dbanalyser compliance-report --db-name LTFS_PROD --packs gdpr --format json
```

**Full compliance bundle (all packs, all formats):**

```bash
for fmt in excel json csv; do
  dbanalyser compliance-report --run-id 99 --format $fmt
done
```

### 13.3 Output file naming

```
output/compliance_report_<run_id>_<timestamp>.<ext>
```

The Excel output has three sheets: **SOX Findings**, **GDPR Findings**, **RBI Findings** — one sheet per enabled pack. Empty sheets are omitted.

---

## 14. Schedule Commands

### 14.1 Overview

The built-in scheduler lets you define recurring analysis tasks without OS-level cron or Windows Task Scheduler. Tasks are stored in PostgreSQL and fired by the scheduler background thread running inside the API process.

### 14.2 `schedule list`

```bash
dbanalyser schedule list
```

Sample output:

```
ID  Name             Cron          DB       Last Run             Next Run
──  ───────────────  ────────────  ───────  ───────────────────  ───────────────────
1   nightly-all      0 2 * * *     all      2026-03-29 02:00:01  2026-03-30 02:00:00
2   weekly-sox       0 6 * * 1     LTFS_PROD  2026-03-23 06:00:02  2026-03-30 06:00:00
```

### 14.3 `schedule add`

```bash
dbanalyser schedule add \
  --name "my-task" \
  --cron "30 3 * * *" \
  --db-name LTFS_DEV \
  --label "auto-$(date +%Y%m%d)"
```

### 14.4 `schedule remove`

```bash
dbanalyser schedule remove --name "my-task"
# Permanently deletes the task from PostgreSQL
```

### 14.5 `schedule run-due`

```bash
dbanalyser schedule run-due
# Immediately fires all tasks whose next_run_at is in the past
# Useful for testing without waiting for the cron time
```

---

## 15. Auth Commands

### 15.1 `auth hash-password`

When `auth.enabled: true` in config, user passwords must be stored as bcrypt hashes. Generate a hash:

```bash
dbanalyser auth hash-password
```

The command prompts twice for the password (with confirmation), then prints the bcrypt hash. Copy it into `analysis_config.yaml`:

```yaml
auth:
  users:
    - username: john.smith
      hashed_password: "$2b$12$abc..."
      roles: [viewer]
```

Do **not** store the plaintext password anywhere in config or version control.

---

## 16. Compliance Dashboard Pages (React UI)

### 16.1 Accessing compliance pages

Click **Compliance** in the left sidebar of the React UI. Select a run from the top bar — compliance findings load automatically.

### 16.2 Compliance Overview tab

- **KPI cards**: Total compliance findings, SOX count, GDPR count, RBI count, Security + Dangerous SQL count
- **Findings by Category** bar chart: count per compliance framework
- **By Severity** donut chart: Critical / High / Medium / Low across all compliance findings

### 16.3 SOX tab

- Full table of Compliance-SOX findings for the selected run
- Click any row to expand the full Issue, Recommendation, and Code Snippet
- Filter available via the search input on the Issues Explorer tab in Analysis

### 16.4 GDPR tab

- Full table of Compliance-GDPR findings
- Expandable rows show PII exposure details and recommended masking techniques

### 16.5 RBI tab

- Full table of Compliance-RBI findings
- Expandable rows show encryption gaps and audit log recommendations

### 16.6 Security tab

- Hardcoded credentials, SQL injection vectors, EXECUTE AS misuse, xp_cmdshell findings

### 16.7 Dangerous SQL tab

- DELETE / TRUNCATE without WHERE clause (DNG001–003)
- DROP TABLE / DROP DATABASE statements (DNG004)
- Missing XACT_ABORT in DML procedures (DNG005–006)
- Each row expandable with the affected code snippet

---

## 17. Webhook Notification Setup

### 17.1 Overview

When notifications are enabled, DBAnalyser sends an alert to Slack and/or Teams at the end of each analysis run — but only when the number of qualifying findings meets `min_findings_to_alert`.

### 17.2 Enable notifications in config

```yaml
notifications:
  enabled: true
  slack_webhook_url: "https://hooks.slack.com/services/..."
  teams_webhook_url: ""                       # leave blank to disable Teams
  alert_on_severity: [Critical, High]
  min_findings_to_alert: 1
```

### 17.3 Test a notification

Trigger a run and check your channel:

```bash
dbanalyser run --no-persist --label "webhook-test"
```

If no findings match `alert_on_severity` or the count is below `min_findings_to_alert`, no message is sent.

### 17.4 Alert content

Each alert includes:
- Database name and run label
- Health score
- Per-severity finding counts (Critical / High / Medium / Low)
- Direct link to the API findings endpoint for that run (when API is accessible from the webhook receiver)

### 17.5 Silence low-noise runs

To only alert on truly problematic runs, raise the threshold:

```yaml
notifications:
  alert_on_severity: [Critical]
  min_findings_to_alert: 1
```

This sends an alert only when at least one Critical finding is detected.
