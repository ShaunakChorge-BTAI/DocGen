# DBAnalyser — Administrator Manual
## Version 2.0.0 | LTFS Technology | March 2026

---

## Table of Contents

1. System Requirements
2. Installation
3. PostgreSQL Setup
4. Configuration Reference
5. Database Registry Management
6. REST API Server Administration
7. Scheduled Tasks (Windows)
8. Backup and Recovery
9. Monitoring and Logs
10. Upgrading
11. Troubleshooting
12. Environment Variables Reference
13. Custom YAML Rules
14. Scheduled Scan Engine
15. JWT Authentication Setup
16. Webhook Notifications
17. Docker Deployment

---

## 1. System Requirements

### Minimum Hardware
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8 GB |
| Disk | 10 GB free | 50 GB free |
| Network | LAN access to SQL Server and PostgreSQL | |

### Software Prerequisites
| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.10+ | 3.12 recommended |
| PostgreSQL | 13+ | For results persistence |
| ODBC Driver | Microsoft ODBC Driver 17 or 18 for SQL Server | Required for live-DB mode |
| pip | 23+ | For package installation |
| Git | 2.x | For source deployment |

---

## 2. Installation

### 2.1 Clone and install

```bash
git clone <repo-url> D:\LTFS\ltfs-analyzer
cd D:\LTFS\ltfs-analyzer

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

# Install all dependencies
pip install -e ".[dev]"

# Verify installation
dbanalyser --version
```

### 2.2 Automated Windows install

A batch script is provided for Windows installations:

```
deployment\install.bat
```

This script:
- Creates the virtual environment
- Installs all pip dependencies
- Validates the Python version
- Verifies the `dbanalyser` command is accessible

### 2.3 Verify installation

```bash
dbanalyser --version
# Expected: DBAnalyser, version 2.0.0

python -m pytest tests/ -q
# Expected: 168 passed
```

### 2.4 Install the React UI

Node.js 18 LTS or later is required.

```bash
cd D:\LTFS\ltfs-analyzer\dbanalyser-ui

# Install npm dependencies
npm install

# Verify TypeScript — should print nothing (zero errors)
npx tsc --noEmit

# Start development server (port 5173)
npm run dev

# Or build for production
npm run build
# Output is written to dbanalyser-ui\dist\
```

**Environment variable:** The UI reads `VITE_API_URL` from a `.env` file in `dbanalyser-ui\`.
Default value: `http://localhost:8000`

```bash
# dbanalyser-ui\.env (create if not present)
VITE_API_URL=http://localhost:8000
```

For production deployment, set `VITE_API_URL` to the public FastAPI hostname/port and rebuild with `npm run build`. Serve the `dist\` folder from any static web server (Nginx, IIS, Azure Static Web Apps).

---

## 3. PostgreSQL Setup

### 3.1 Create the database

```sql
-- Run as PostgreSQL superuser
CREATE DATABASE dbanalyser;
CREATE USER dbanalyser_user WITH PASSWORD 'change_this_password';
GRANT ALL PRIVILEGES ON DATABASE dbanalyser TO dbanalyser_user;
```

### 3.2 Configure connection

Edit `analysis_config.yaml`:

```yaml
postgres:
  host:      "localhost"
  port:      5432
  database:  "dbanalyser"
  user:      "dbanalyser_user"
  password:  ""               # set via env var — see section 12
  db_schema: "public"
  min_conn:  1
  max_conn:  5
```

Or set via environment variable:
```bash
set DBANALYSER_POSTGRES_PASSWORD=change_this_password
```

### 3.3 Initialise the schema

```bash
dbanalyser init-db --config analysis_config.yaml
```

Expected output:
```
Creating PostgreSQL schema …
  ✓ Schema created / verified.

  Next step: dbanalyser db sync  (imports databases from config)
```

This creates tables: `db_registry`, `runs`, `findings`, `health_trend`, `scheduled_tasks`, `jobs` and all supporting indexes and triggers.

### 3.4 Verify schema

```sql
-- Connect to the dbanalyser database
\dt
-- Should show: db_registry, findings, health_trend, jobs, runs, scheduled_tasks
```

---

## 4. Configuration Reference

All settings live in `analysis_config.yaml`. Every value can be overridden via environment variable `DBANALYSER_<SECTION>_<KEY>`.

### 4.1 Source configuration

```yaml
source:
  mode: file                      # "file" | "live_db"
  file_path: "D:\\LTFS"           # root path for file-mode scan
  file_extensions: [".sql", ".ddl"]
  recursive: true
  connection_string: ""           # for live_db mode
```

### 4.2 Scope filters

```yaml
scope:
  object_types:
    - "Stored Procedure"
    - "View"
    - "Table"
    - "Function"
    - "Trigger"
  schemas: []                     # [] = all schemas
  exclude_schemas: [sys, INFORMATION_SCHEMA]
  include_patterns: []            # glob patterns e.g. ["usp_*", "vw_*"]
  exclude_patterns: []
  exclude_system_objects: true
  max_object_size_kb: 500
```

### 4.3 Analysis toggles

```yaml
analysis:
  categories:
    security:            true
    reliability:         true
    performance:         true
    data_safety:         true
    best_practices:      true
    parameter_sniffing:  true
    maintainability:     true
  enable_pk_check:         true
  enable_col_mismatches:   true
  enable_unused_joins:     true
```

### 4.4 REST API

```yaml
api:
  api_key: ""              # leave blank = open access; set for production
  host:    "0.0.0.0"       # bind interface
  port:    8000
  reload:  false           # never true in production
```

### 4.5 Compliance packs

```yaml
compliance:
  enabled_packs: []        # e.g. [sox, gdpr, rbi]
  financial_schemas: [dbo]
  audit_tables: []
  pii_column_patterns:
    - email
    - phone
    - ssn
    - dob
    - passport
  financial_tables: []
  require_rls: false
```

### 4.6 Custom rules

```yaml
custom_rules:
  enabled: false
  rules_dir: ./custom_rules   # directory scanned for *.yaml rule files
  rules_files: []             # explicit list of rule files (overrides rules_dir when set)
```

See section 13 for full custom rule authoring instructions.

### 4.7 Notifications

```yaml
notifications:
  enabled: false
  slack_webhook_url: ""
  teams_webhook_url: ""
  alert_on_severity: [Critical, High]   # severities that trigger an alert
  min_findings_to_alert: 1              # send alert only when at least N findings match
```

Webhooks are fired at the end of each analysis run when the finding count meets the threshold.

### 4.8 Scheduler

```yaml
scheduler:
  enabled: false
  check_interval_sec: 60    # how often the scheduler polls for due tasks
```

See section 14 for full scheduler setup.

### 4.9 Authentication (JWT RBAC)

```yaml
auth:
  enabled: false
  secret_key: "change-me-in-production"   # MUST be changed before production use
  algorithm: HS256
  token_expire_minutes: 480               # 8 hours
  users: []                               # list of {username, hashed_password, roles}
```

See section 15 for user management and JWT token workflow.

### 4.10 Performance tuning

```yaml
performance:
  parallel_workers:        4      # increase for faster scans on multi-core systems
  max_procedure_lines:     500    # MNT001 threshold
  max_nesting_depth:       4      # MNT002 threshold
  max_parameters:          15     # MNT003 threshold
  slow_query_threshold_ms: 1000
```

---

## 5. Database Registry Management

### 5.1 Sync from config

After adding databases to `analysis_config.yaml`:

```bash
dbanalyser db sync
```

### 5.2 Add a database directly

```bash
dbanalyser db add LTFS_PROD \
  --env production \
  --host prod-sql-server \
  --port 1433 \
  --db LTFS_Production \
  --owner "DBA Team"
```

### 5.3 List registered databases

```bash
dbanalyser db list            # active only
dbanalyser db list --all      # include inactive
```

### 5.4 Show details for one database

```bash
dbanalyser db show LTFS_PROD
```

Output includes: host, environment, owner, last run timestamp, health score, last 5 runs.

### 5.5 Deactivate a database

```bash
dbanalyser db remove LTFS_OLD
# Soft-delete — data is retained, database excluded from --all-dbs runs
```

### 5.6 Validate connections

```bash
dbanalyser validate                      # all active databases + PostgreSQL
dbanalyser validate --db-name LTFS_PROD  # one specific database
```

---

## 6. REST API Server Administration

### 6.1 Start the API server

```bash
# Via CLI (recommended — loads config automatically)
dbanalyser api --config analysis_config.yaml --port 8000

# Via uvicorn directly
uvicorn dbanalyser.api.main:app --host 0.0.0.0 --port 8000

# Development mode with auto-reload
dbanalyser api --reload
```

### 6.2 Set an API key

**Option A** — via config file:
```yaml
api:
  api_key: "your-strong-random-key-here"
```

**Option B** — via environment variable (recommended for production):
```bash
set DBANALYSER_API_API_KEY=your-strong-random-key-here
dbanalyser api
```

**Option C** — via CLI flag:
```bash
dbanalyser api --api-key your-strong-random-key-here
```

Once set, all API calls must include:
```
X-API-Key: your-strong-random-key-here
```
or `?api_key=your-strong-random-key-here`

### 6.3 Verify the API is running

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"DBAnalyser API","version":"2.0.0"}
```

### 6.4 Swagger UI

Navigate to: `http://localhost:8000/docs`

Click **Authorize** and enter the API key to test authenticated endpoints.

### 6.5 Running as a Windows Service

Use NSSM (Non-Sucking Service Manager) or Windows Task Scheduler.
A Task Scheduler template is provided at `deployment\task_scheduler_template.xml`.

```bash
# Import the task (modify paths in XML first)
schtasks /create /xml deployment\task_scheduler_template.xml /tn "DBAnalyser API"
```

---

## 7. Scheduled Tasks (Windows)

### 7.1 Configure a scheduled analysis run

1. Edit `deployment\task_scheduler_template.xml` — update `<WorkingDirectory>` and `<Arguments>`
2. Import via Task Scheduler UI or:

```bash
schtasks /create /xml deployment\task_scheduler_template.xml /tn "DBAnalyser Nightly"
```

### 7.2 Recommended schedule

| Task | Suggested Schedule | Command |
|------|--------------------|---------|
| Nightly analysis (all DBs) | Daily 02:00 | `dbanalyser run --all-dbs --label nightly` |
| Weekly compliance report | Monday 06:00 | `dbanalyser run --all-dbs --label weekly_sox` (with `enabled_packs: [sox]`) |
| API server watchdog | On system startup | `dbanalyser api --port 8000` |

---

## 8. Backup and Recovery

### 8.1 PostgreSQL backup

```bash
# Full backup
pg_dump -U dbanalyser_user -d dbanalyser -Fc -f dbanalyser_backup_$(date +%Y%m%d).dump

# Restore
pg_restore -U dbanalyser_user -d dbanalyser dbanalyser_backup_20260330.dump
```

### 8.2 Configuration backup

```bash
# Back up config and deployment files
copy analysis_config.yaml analysis_config.yaml.bak
```

### 8.3 What data is stored

| Table | Rows | Retention recommendation |
|-------|------|--------------------------|
| db_registry | One per registered database | Permanent |
| runs | One per analysis run | 2 years |
| findings | One per finding per run | 2 years |
| health_trend | One per run per database | Permanent (drives trend charts) |

---

## 9. Monitoring and Logs

### 9.1 Log configuration

```yaml
run:
  log_level: "INFO"    # DEBUG | INFO | WARNING | ERROR
  log_file:  ""        # leave blank = stdout; set path for file logging
```

### 9.2 Key log messages to watch

| Pattern | Meaning |
|---------|---------|
| `PostgreSQL pool init failed` | PostgreSQL unreachable — API starts in degraded mode, persistence disabled |
| `Analysis failed for <schema>.<name>` | Individual rule or object error — analysis continues |
| `Extended checks partially failed` | Non-critical — schema cross-checks skipped |
| `Persisted N findings (run_id=N)` | Successful persistence confirmation |
| `Analysis complete in X.Xs` | Normal completion with timing |

### 9.3 Health check endpoint

```bash
curl http://localhost:8000/health
# {"status": "ok", "service": "DBAnalyser API", "version": "2.0.0"}
```

Integrate with your monitoring tool (Zabbix, Nagios, Prometheus blackbox exporter) to alert when this returns non-200.

---

## 10. Upgrading

### 10.1 Standard upgrade

```bash
cd D:\LTFS\ltfs-analyzer
git pull
pip install -e ".[dev]"

# Re-run schema migration (safe to run on existing schema — uses IF NOT EXISTS)
dbanalyser init-db

# Verify
python -m pytest tests/ -q
dbanalyser --version
```

### 10.2 Config file migration

When upgrading, check `analysis_config.yaml` against the new defaults.
Old key names are preserved via backward-compatible aliases — no forced migration.

New sections added in v2.0.0:
- `api:` — REST API server settings
- `compliance:` — compliance pack settings
- `databases:` — multi-DB registry

New sections added in Phase C / D:
- `custom_rules:` — YAML-driven custom rule authoring
- `notifications:` — Slack / Teams webhook alerts
- `scheduler:` — built-in scheduled scan engine
- `auth:` — JWT RBAC user authentication

---

## 11. Troubleshooting

### PostgreSQL connection refused
```
PostgreSQL pool init failed: connection refused
```
- Check PostgreSQL service is running: `pg_ctl status -D <data_dir>`
- Verify host, port, user, password in config
- Check pg_hba.conf allows the connection
- Try: `psql -h localhost -U dbanalyser_user -d dbanalyser`

### SQL Server connection failed (live-DB mode)
```
pyodbc.OperationalError: [08001] ...
```
- Verify ODBC Driver 17 is installed: `odbcad32.exe` → Drivers tab
- Test DSN: `dbanalyser validate --db-name <NAME>`
- Check Windows Authentication / firewall on port 1433
- For named instances use `SERVER=host\instance`

### No SQL objects found
```
Loaded 0 objects
```
- Verify `source.file_path` points to a directory containing `.sql` files
- Check `scope.object_types` — ensure the types present in your files are listed
- Run with `--verbose` to see per-file scan logs

### API key rejected (HTTP 401)
- Confirm the key in the request header matches `api.api_key` in config
- Header name is case-sensitive: `X-API-Key` (not `x-api-key`)
- If `api_key` is blank, the API is open — no header needed

### Test suite failures
```bash
python -m pytest tests/ -v --tb=long
```
- If `good_proc.sql` produces Critical/High findings, a new rule may need the fixture updated
- Check `CLAUDE.md` gotchas section for known patterns

### High memory usage during large scans
- Reduce `performance.parallel_workers` to 2
- Set `scope.max_object_size_kb: 200` to skip very large files
- Set `performance.max_objects_to_scan: 500` to limit batch size

---

## 12. Environment Variables Reference

All environment variables follow the pattern `DBANALYSER_<SECTION>_<KEY>`.

| Variable | Config Equivalent | Example |
|----------|-------------------|---------|
| `DBANALYSER_POSTGRES_PASSWORD` | `postgres.password` | `SecretPass123` |
| `DBANALYSER_POSTGRES_HOST` | `postgres.host` | `prod-pg-server` |
| `DBANALYSER_POSTGRES_PORT` | `postgres.port` | `5432` |
| `DBANALYSER_POSTGRES_DATABASE` | `postgres.database` | `dbanalyser_prod` |
| `DBANALYSER_POSTGRES_USER` | `postgres.user` | `dbanalyser_user` |
| `DBANALYSER_API_API_KEY` | `api.api_key` | `my-secret-key` |
| `DBANALYSER_API_PORT` | `api.port` | `8000` |
| `DBANALYSER_SOURCE_MODE` | `source.mode` | `live_db` |
| `DBANALYSER_SOURCE_FILE_PATH` | `source.file_path` | `D:\LTFS\sql` |
| `DBANALYSER_RUN_ENVIRONMENT` | `run.environment` | `production` |
| `DBANALYSER_RUN_LOG_LEVEL` | `run.log_level` | `WARNING` |
| `DBANALYSER_AUTH_SECRET_KEY` | `auth.secret_key` | `my-jwt-secret-256bit` |
| `DBANALYSER_AUTH_ENABLED` | `auth.enabled` | `true` |
| `DBANALYSER_NOTIFICATIONS_SLACK_WEBHOOK_URL` | `notifications.slack_webhook_url` | `https://hooks.slack.com/...` |
| `DBANALYSER_NOTIFICATIONS_TEAMS_WEBHOOK_URL` | `notifications.teams_webhook_url` | `https://outlook.office.com/...` |
| `DBANALYSER_SCHEDULER_ENABLED` | `scheduler.enabled` | `true` |
| `DBANALYSER_CUSTOM_RULES_ENABLED` | `custom_rules.enabled` | `true` |

Environment variables take precedence over `analysis_config.yaml` values.

---

## 13. Custom YAML Rules

### 13.1 Overview

Custom rules let teams define organisation-specific checks in YAML without writing Python. Each rule file is a `.yaml` file containing one or more rule definitions. Rules are loaded at startup when `custom_rules.enabled: true`.

### 13.2 Directory layout

```
project-root/
  custom_rules/
    naming_conventions.yaml
    ltfs_financial_checks.yaml
```

Point the config at this directory:

```yaml
custom_rules:
  enabled: true
  rules_dir: ./custom_rules
```

Or enumerate files explicitly (useful when rules live outside the project):

```yaml
custom_rules:
  enabled: true
  rules_files:
    - /shared/rules/corporate_standards.yaml
    - ./custom_rules/local_overrides.yaml
```

### 13.3 Rule file format

```yaml
# custom_rules/example.yaml
rules:
  - id: CUSTOM001
    name: "No cursors allowed"
    category: Performance
    severity: High
    description: "Cursors degrade performance — use set-based operations instead."
    recommendation: "Replace cursor logic with a single set-based INSERT/UPDATE/SELECT."
    patterns:
      - DECLARE\s+\w+\s+CURSOR     # regex matched against uppercased source
    applies_to: [Stored Procedure, Function]  # omit = all object types

  - id: CUSTOM002
    name: "Require schema prefix on all objects"
    category: Best Practices
    severity: Low
    description: "All object references must include a two-part name (schema.object)."
    recommendation: "Replace bare object names with schema-qualified names e.g. dbo.TableName."
    patterns:
      - \bFROM\s+[A-Za-z_]\w+\b(?!\s*\.)
    applies_to: [Stored Procedure, View]
```

### 13.4 Supported fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique rule identifier — use CUSTOM prefix |
| `name` | Yes | Short human-readable rule name |
| `category` | Yes | Any string — appears in findings output |
| `severity` | Yes | Critical / High / Medium / Low |
| `description` | Yes | Issue text shown in the finding |
| `recommendation` | Yes | Remediation text shown in the finding |
| `patterns` | Yes | List of Python regex patterns (one match = one finding) |
| `applies_to` | No | List of object types; omit to apply to all |
| `enabled` | No | `false` to temporarily disable a rule |

### 13.5 Verify custom rules loaded

```bash
dbanalyser run --no-persist --verbose 2>&1 | grep CUSTOM
# Should show: Loaded custom rule CUSTOM001, CUSTOM002 ...
```

---

## 14. Scheduled Scan Engine

### 14.1 Overview

Phase D introduces a built-in scheduler so DBAnalyser can run periodic analyses without relying on the OS task scheduler. Scheduled tasks are stored in the `scheduled_tasks` PostgreSQL table and checked every `scheduler.check_interval_sec` seconds while the API server is running.

### 14.2 Enable the scheduler

```yaml
scheduler:
  enabled: true
  check_interval_sec: 60
```

The scheduler runs as a background thread inside the API process. The API must be running for scheduled tasks to fire.

### 14.3 Manage scheduled tasks via CLI

```bash
# List all scheduled tasks
dbanalyser schedule list

# Add a new task
dbanalyser schedule add \
  --name "nightly-all-dbs" \
  --cron "0 2 * * *" \
  --db-name all \
  --label "nightly"

# Remove a task by name or ID
dbanalyser schedule remove --name "nightly-all-dbs"

# Manually trigger all tasks that are currently due (useful for testing)
dbanalyser schedule run-due
```

### 14.4 `scheduled_tasks` table

| Column | Description |
|--------|-------------|
| id | BIGSERIAL PK |
| name | Human-readable task name |
| cron_expression | Standard 5-field cron string (UTC) |
| db_name | Target database name or `all` |
| label_template | Label applied to triggered runs |
| is_active | Boolean — set false to pause a task |
| last_run_at | Timestamp of last execution |
| next_run_at | Pre-computed next fire time |
| created_at | Audit timestamp |

### 14.5 `jobs` table

Async analysis jobs (API-triggered and scheduler-triggered) are persisted in the `jobs` table:

| Column | Description |
|--------|-------------|
| id | UUID PK (job_id string) |
| status | queued / running / done / failed |
| db_name | Target database |
| label | Run label |
| run_id | FK to `runs.id` once complete |
| error | Error message if failed |
| created_at / updated_at | Audit timestamps |

---

## 15. JWT Authentication Setup

### 15.1 Overview

When `auth.enabled: true` the API enforces JWT Bearer token authentication in addition to (or instead of) the static API key. Tokens are issued via `POST /auth/token` and validated on every protected endpoint.

### 15.2 Enable auth

```yaml
auth:
  enabled: true
  secret_key: "replace-with-256-bit-random-string"
  algorithm: HS256
  token_expire_minutes: 480
  users: []
```

Generate a strong secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set it via environment variable for production (never commit it to version control):
```bash
set DBANALYSER_AUTH_SECRET_KEY=<generated-value>
```

### 15.3 Add users

Hash a password using the CLI:
```bash
dbanalyser auth hash-password
# Prompts for password, prints bcrypt hash
```

Add the user to config:
```yaml
auth:
  enabled: true
  secret_key: "..."
  users:
    - username: dba_admin
      hashed_password: "$2b$12$..."   # output from hash-password
      roles: [admin]
    - username: readonly_user
      hashed_password: "$2b$12$..."
      roles: [viewer]
```

Supported roles: `admin` (full access), `viewer` (read-only endpoints).

### 15.4 Obtain a token

```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=dba_admin&password=yourpassword"
```

Response:
```json
{"access_token": "eyJhbGci...", "token_type": "bearer"}
```

### 15.5 Use the token

```bash
curl -H "Authorization: Bearer eyJhbGci..." \
  http://localhost:8000/databases
```

### 15.6 Inspect current user

```bash
curl -H "Authorization: Bearer eyJhbGci..." \
  http://localhost:8000/auth/me
```

Response:
```json
{"username": "dba_admin", "roles": ["admin"]}
```

### 15.7 `dbanalyser auth` CLI group

```bash
dbanalyser auth hash-password     # Interactively hash a plaintext password
```

---

## 16. Webhook Notifications

### 16.1 Overview

DBAnalyser can POST a JSON summary to Slack and/or Microsoft Teams after each analysis run when findings meet the configured threshold.

### 16.2 Slack setup

1. Create an Incoming Webhook in your Slack workspace: **Workspace Settings → Manage Apps → Incoming Webhooks → Add New Webhook**.
2. Copy the webhook URL and add it to config:

```yaml
notifications:
  enabled: true
  slack_webhook_url: "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
  alert_on_severity: [Critical, High]
  min_findings_to_alert: 1
```

3. Confirm alerts are firing:
```bash
dbanalyser run --no-persist
# Check your Slack channel for an alert message
```

### 16.3 Microsoft Teams setup

1. In the target Teams channel: **... → Connectors → Incoming Webhook → Configure**.
2. Copy the webhook URL:

```yaml
notifications:
  enabled: true
  teams_webhook_url: "https://outlook.office.com/webhook/..."
  alert_on_severity: [Critical]
  min_findings_to_alert: 0
```

Setting `min_findings_to_alert: 0` sends a notification even when there are no findings (useful for confirming the scan ran).

### 16.4 Alert payload format

Slack message example (adaptive card summary):
```
DBAnalyser Alert — LTFS_PROD
Run: nightly-20260330 | Health: 74.5
Critical: 2 | High: 5 | Medium: 11 | Low: 8
```

Teams message uses an Adaptive Card with the same fields.

---

## 17. Docker Deployment

### 17.1 Overview

A `Dockerfile` and `docker-compose.yml` are provided in the project root for containerised deployment. The container runs the API server on port 8000 by default.

### 17.2 Build and run with Docker Compose

```bash
# From the project root
docker compose up --build -d
```

This starts two services:
- `dbanalyser-api` — FastAPI application on port 8000
- `postgres` — PostgreSQL 15 on port 5432 (internal network only)

Check the API is running:
```bash
curl http://localhost:8000/health
```

### 17.3 Environment variables for Docker

Pass sensitive values via a `.env` file (never commit it):

```bash
# .env  (gitignored)
DBANALYSER_POSTGRES_PASSWORD=strong_password_here
DBANALYSER_API_API_KEY=my-api-key
DBANALYSER_AUTH_SECRET_KEY=my-jwt-secret
```

`docker-compose.yml` picks these up automatically via `env_file: .env`.

### 17.4 Initialise the schema in Docker

```bash
docker compose exec dbanalyser-api dbanalyser init-db
```

### 17.5 Dockerfile highlights

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[prod]"
EXPOSE 8000
CMD ["dbanalyser", "api", "--host", "0.0.0.0", "--port", "8000"]
```

### 17.6 Production considerations

- Mount a named volume for `/app/output` to persist generated reports
- Use a managed PostgreSQL service (Azure Database for PostgreSQL, AWS RDS) rather than the bundled container in production
- Set `api.reload: false` (default) — never enable hot-reload in production containers
- Rotate `auth.secret_key` and `api.api_key` via Kubernetes secrets or Docker secrets
