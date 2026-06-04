# DBAnalyser — Application Tech Stack
## Version 2.0.0 | LTFS Technology | April 2026

---

## Table of Contents

1. Architecture Overview
2. Backend — Python / FastAPI
3. Frontend — React UI
4. Database Layer
5. Analysis Engine
6. Infrastructure & Tooling
7. Third-Party Integrations
8. Dependency Versions

---

## 1. Architecture Overview

DBAnalyser is a **full-stack intelligence platform** for SQL Server analysis. It follows a three-tier architecture:

```
┌─────────────────────────────────────┐
│  React UI  (Vite + TypeScript)      │  http://localhost:5173
│  Browser SPA — "The Lucid Architect"│
└─────────────────┬───────────────────┘
                  │ HTTP / REST + JSON
                  │ Bearer token (JWT) or anonymous
┌─────────────────▼───────────────────┐
│  FastAPI Backend  (Python 3.10+)    │  http://localhost:8000
│  REST API + Analysis Engine         │
└─────────────────┬───────────────────┘
                  │ asyncpg / psycopg2
┌─────────────────▼───────────────────┐
│  PostgreSQL 13+                     │  Persistence: runs, findings, databases
└─────────────────────────────────────┘
                  │ pyodbc / ODBC 17/18
┌─────────────────▼───────────────────┐
│  Microsoft SQL Server               │  Source of SQL code / DMV data
└─────────────────────────────────────┘
```

The React UI is a **Single-Page Application (SPA)** that communicates exclusively with the FastAPI backend via REST. The backend runs the analysis engine, persists results to PostgreSQL, and serves them to the UI.

---

## 2. Backend — Python / FastAPI

### 2.1 Runtime

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.10+ (3.12 recommended) |
| HTTP Framework | FastAPI | 0.110+ |
| ASGI Server | Uvicorn | 0.29+ |
| Data Validation | Pydantic v2 | 2.x |

### 2.2 Key Python packages

| Package | Purpose |
|---------|---------|
| `fastapi` | REST API framework |
| `uvicorn[standard]` | ASGI server with HTTP/2 |
| `pydantic` | Settings validation, request/response models |
| `sqlalchemy` | ORM for PostgreSQL access |
| `psycopg2-binary` | PostgreSQL driver |
| `pyodbc` | ODBC connection to SQL Server (live-DB mode) |
| `openpyxl` | Excel report generation |
| `jinja2` | HTML report templating |
| `python-jose[cryptography]` | JWT encoding/decoding |
| `passlib[bcrypt]` | Password hashing |
| `click` | CLI command framework |
| `pyyaml` | Config file parsing |
| `requests` | Webhook HTTP calls (Slack / Teams) |
| `pytest` | Test runner |
| `pytest-asyncio` | Async test support |

### 2.3 API design

- **RESTful JSON API** — all endpoints return `application/json`
- **OpenAPI / Swagger UI** available at `http://localhost:8000/docs`
- **Authentication**: JWT Bearer tokens or anonymous (when `auth.enabled: false`)
- **CORS**: configured to allow requests from `http://localhost:5173` (dev) and production origin
- **Key endpoint groups**:

| Prefix | Purpose |
|--------|---------|
| `GET /health` | Server health check |
| `POST /auth/login` | Obtain JWT token |
| `GET /auth/me` | Current user info |
| `GET /databases` | List registered SQL Server databases |
| `POST /databases` | Register a new database |
| `DELETE /databases/{name}` | Remove a database |
| `GET /runs` | List analysis runs (filterable by db_name) |
| `POST /runs/trigger` | Trigger a new analysis run |
| `GET /findings/run/{run_id}` | All findings for a run |
| `GET /findings/summary/{run_id}` | Severity count summary |
| `GET /schema/` | Schema objects for a run |
| `GET /schema/summary` | Schema quality KPIs |
| `GET /reports/download/{run_id}` | Download report file |
| `GET /reports/health-gate/{run_id}` | Health gate pass/fail |
| `GET /trend/all` | Health score time-series per database |
| `GET /audit/` | Audit log entries |

### 2.4 Analysis engine modules

| Module | Description |
|--------|-------------|
| `engine/rules.py` | Rule registry and rule set builder |
| `engine/analyser.py` | Main analysis pipeline — scan → apply rules → persist |
| `engine/scanner.py` | SQL file scanner (reads DDL, extracts object metadata) |
| `engine/live_db.py` | DMV queries for live-DB performance checks |
| `engine/report.py` | Excel / HTML / CSV / JSON report writers |
| `engine/compliance/` | SOX, GDPR, RBI compliance rule packs |
| `engine/custom_rules.py` | YAML-defined custom rule loader |
| `engine/scheduler.py` | Cron-based scheduled scan engine |
| `engine/webhooks.py` | Slack / Teams notification sender |

---

## 3. Frontend — React UI

### 3.1 Core framework

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | TypeScript | 5.x |
| UI Framework | React | 19.x |
| Build Tool | Vite | 5.x |
| CSS Framework | Tailwind CSS | 3.x |
| Routing | React Router v7 | 7.x |
| Data Fetching | TanStack Query (React Query) | 5.x |
| HTTP Client | Axios | 1.x |
| Charts | Recharts | 3.x |
| Icons | Google Material Symbols Outlined | (CDN font) |
| Font | Inter | (Google Fonts CDN) |

### 3.2 Design system — "The Lucid Architect"

| Token | Value |
|-------|-------|
| Primary | `#630ed4` / `#7c3aed` |
| Surface | `#17131f` (darkest) → `#1f1829` → `#271f33` |
| On-surface | `#f4f0ff` (text), `#a89ec0` (variant) |
| Error | `#dc2626` |
| Warning | `#f59e0b` |
| Success | `#10b981` |
| Border radius | `xl` (12px) / `2xl` (16px) |
| Shadow | `shadow-card` (tonal) / `shadow-float` (elevated) |

Custom Tailwind tokens defined in `tailwind.config.js`:
```
surface, surface-low, surface-lowest
on-surface, on-surface-variant
primary, primary-variant
error, warning, success
shadow-card, shadow-float
```

### 3.3 Page structure

| Route | Component | Description |
|-------|-----------|-------------|
| `/login` | `LoginPage` | Sign-in and new organisation registration |
| `/dashboard` | `DashboardPage` | Estate overview, DB cards, trend, run history |
| `/analysis` | `AnalysisPage` | Findings explorer, category + severity charts |
| `/schema-quality` | `SchemaQualityPage` | Schema health: PK, indexes, columns, orphans |
| `/compliance` | `CompliancePage` | SOX / GDPR / RBI / Security / Dangerous SQL |
| `/reports` | `ReportsPage` | Download reports, health gate, trend, audit log |
| `/live-db` | `LiveDbPage` | Live DMV findings, trigger live scan |
| `/administration` | `AdministrationPage` | Databases, schedules, users, system |
| `/run-assessment` | `RunAssessmentPage` | Trigger ad-hoc assessment with options |

### 3.4 Shared components

| Component | Purpose |
|-----------|---------|
| `Layout` | Shell with sidebar + top bar; provides `selectedDb` / `selectedRun` context |
| `TopBar` | Database selector, run selector, user indicator |
| `Sidebar` | Navigation links with Material Symbols icons |
| `PageHeader` | Page title, subtitle, optional action buttons |
| `TabBar` | Tab navigation strip |
| `KpiCard` | Metric card with icon, value, and colour accent |
| `SeverityBadge` | Colour-coded pill for Critical / High / Medium / Low |

### 3.5 State management

- **Server state**: TanStack Query with automatic caching, background refetch, and `queryKey` scoping by `[runId, dbName]`
- **UI state**: React `useState` hooks (tab, filters, form values)
- **Auth state**: React Context (`AuthContext`) — calls `GET /auth/me` on mount; stores token in `localStorage`
- **Schedules**: `localStorage` (no backend schedule endpoint; frontend-managed)

### 3.6 Security

- Bearer token sent in `Authorization` header via Axios interceptor
- `401` responses on non-auth endpoints redirect to `/login`
- Auth-disabled mode: `/auth/me` returns `{username: "anonymous", role: "admin"}` → auto-login
- Download buttons use `fetch()` with `Authorization` header (not plain `<a href>` links) to avoid auth bypass

---

## 4. Database Layer

### 4.1 PostgreSQL schema

| Table | Description |
|-------|-------------|
| `databases` | Registered SQL Server databases (name, host, port, credentials) |
| `runs` | Analysis run metadata (db_name, label, timestamp, health_score, total_issues) |
| `findings` | Individual findings (run_id FK, rule_id, category, severity, object_name, issue, recommendation) |
| `schema_objects` | Schema inventory from each run (tables, views, procedures, triggers) |
| `audit_log` | System events (triggered via API or CLI) |
| `users` | (Optional when auth enabled) username, hashed_password, role |

### 4.2 Connection

- Python: `psycopg2-binary` via SQLAlchemy ORM
- Config: `database.host / port / name / user / password` in `analysis_config.yaml`
- Initialise schema: `dbanalyser init-db`

---

## 5. Analysis Engine

### 5.1 Rule categories

| Category | Rule IDs | Count |
|----------|---------|-------|
| Security | SEC001–005 | 5 |
| Reliability | REL001–004 | 4 |
| Performance | PERF001–008 | 8 |
| Data Safety | DS001–006 | 6 |
| Best Practices | BP001–005 | 5 |
| Parameter Sniffing | PS001–004 | 4 |
| Maintainability | MAINT001–006 | 6 |
| Dangerous SQL | DNG001–006 | 6 |
| Compliance — SOX | SOX001–006 | 6 |
| Compliance — GDPR | GDPR001–006 | 6 |
| Compliance — RBI | RBI001–006 | 6 |
| **Total (all packs)** | | **62** |

### 5.2 Health score formula

```
Health = 100 - (Critical × 5) - (High × 2) - (Medium × 0.5) - (Low × 0.1)
Minimum: 0
```

### 5.3 Source modes

| Mode | How SQL is obtained |
|------|-------------------|
| `file` | Reads `.sql` files from `source.file_path` |
| `live_db` | Connects to SQL Server via ODBC, retrieves object definitions from `sys.sql_modules` |

---

## 6. Infrastructure & Tooling

| Tool | Purpose |
|------|---------|
| **Git** | Source control |
| **pytest** | Python unit and integration tests |
| **ESLint** | TypeScript/React linting |
| **TypeScript** | Static type checking (`npx tsc --noEmit`) |
| **Vite** | React dev server and production bundler |
| **Tailwind CSS CLI** | Utility CSS generation |
| **npm** | Node package manager for frontend |
| **pip** | Python package manager for backend |
| **python-venv** | Isolated Python environment (`.venv\`) |
| **Windows Task Scheduler** | (Optional) OS-level scheduling for `schedule run-due` |

### 6.1 Development workflow

```bash
# Backend
.venv\Scripts\activate
python3 -m dbanalyser api          # http://localhost:8000

# Frontend (separate terminal)
cd dbanalyser-ui
npm run dev                         # http://localhost:5173

# Tests
python -m pytest tests/ -v
cd dbanalyser-ui && npx tsc --noEmit
```

### 6.2 Production build

```bash
cd dbanalyser-ui
npm run build                       # Output in dbanalyser-ui/dist/
# Serve dist/ via Nginx or any static file server
# Point API_URL to production FastAPI host
```

---

## 7. Third-Party Integrations

| Integration | Protocol | When used |
|-------------|---------|-----------|
| **Slack** | HTTPS Webhook (POST) | Run complete alerts (`notifications.slack_webhook_url`) |
| **Microsoft Teams** | HTTPS Adaptive Card Webhook | Run complete alerts (`notifications.teams_webhook_url`) |
| **CI/CD pipeline** | Exit code + JSON output | `dbanalyser run` exits non-zero when Critical findings exceed threshold |
| **JIRA** | CSV import (manual) | Export findings CSV, bulk-import as JIRA tickets |

---

## 8. Dependency Versions

### 8.1 Python requirements (key packages)

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pydantic>=2.0.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
pyodbc>=5.0.0
openpyxl>=3.1.0
jinja2>=3.1.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
click>=8.1.0
pyyaml>=6.0.0
requests>=2.31.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

### 8.2 Node / npm dependencies (key packages)

```json
{
  "react": "^19.2.4",
  "react-dom": "^19.2.4",
  "react-router-dom": "^7.13.2",
  "@tanstack/react-query": "^5.96.1",
  "axios": "^1.14.0",
  "recharts": "^3.8.1",
  "typescript": "^5.x",
  "vite": "^5.x",
  "tailwindcss": "^3.x",
  "eslint": "^9.x"
}
```

### 8.3 Runtime prerequisites

| Component | Minimum version | Notes |
|-----------|----------------|-------|
| Python | 3.10 | 3.12 recommended |
| Node.js | 20 LTS | 22 LTS recommended |
| npm | 10 | Ships with Node 20 |
| PostgreSQL | 13 | 15+ recommended |
| Microsoft ODBC Driver | 17 | 18 recommended |
| Git | 2.x | For source deployment |

---

*Document maintained by LTFS Technology — DBAnalyser Engineering Team.*
*Last updated: April 2026*
