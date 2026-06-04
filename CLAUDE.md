# DBAnalyser — Claude Code Project Guide

> Read this entire file before touching any code.
> It encodes every architectural decision, every gotcha found in development,
> and every convention the codebase depends on.
>
> **Status (2026-04-01)**: Phases A–F complete. Dashboard fully operational with real data.
> 1,531 schema objects ingested. Live DB data imported from XLS. Dashboard at http://localhost:8506.
> Health check: `python health_check.py` — all 14 checks pass.

---

## Project overview

Enterprise SQL Server code-quality, performance, and compliance analyser for LTFS.
Scans SQL objects (Stored Procedures, Views, Tables, Triggers, Functions) from
file trees or live SQL Server connections, runs a rule engine, grades findings
Critical / High / Medium / Low, and persists results to PostgreSQL for trend analysis.
Includes AI-powered SQL optimization via Anthropic Claude.

**Stack**: Python 3.10+  ·  FastAPI + uvicorn  ·  React 19 (Vite)  ·
PostgreSQL (psycopg2)  ·  Click CLI  ·  Pydantic v2  ·  pandas / openpyxl  ·
Anthropic Claude API (optional)

---

## Installation

```bash
# Core (analysis, API)
pip install -e .

# With AI optimizer support
pip install -e ".[ai]"          # adds anthropic

# With high-quality embeddings
pip install -e ".[embeddings]"  # adds sentence-transformers

# Everything
pip install -e ".[all]"
```

**Verify installation:**
```bash
python health_check.py          # 14 checks — all must pass
python -m pytest tests/ -v      # 246 tests — 0 failures
```

---

## Repository layout

```
D:\LTFS\ltfs-analyzer\
├── analysis_config.yaml          <- default config loaded by CLI and API
├── pyproject.toml                <- deps, pytest config, ruff config
├── health_check.py               <- 14-point installation health check
├── CLAUDE.md                     <- this file
├── Dockerfile                    <- multi-stage Python 3.12-slim
├── docker-compose.yml            <- postgres + api + pgadmin
├── dbanalyser/
│   ├── config.py                 <- Settings (Pydantic v2) — single source of truth
│   ├── cli.py                    <- Click command group: main() — 14 commands
│   ├── schema_intel/             <- Vector knowledge base for schema intelligence
│   │   ├── embedder.py           <- TF-IDF 256-dim embeddings (pure Python)
│   │   ├── extractor.py          <- Extract schema from live DB or SQL files
│   │   ├── repository.py         <- upsert/query schema_objects table
│   │   └── searcher.py           <- cosine similarity search + context builder
│   ├── ai_optimizer/             <- Anthropic Claude SQL optimizer
│   │   ├── optimizer.py          <- optimize_sql_object() — main entry point
│   │   └── context_builder.py    <- build_optimization_context() — CALL FIRST
│   ├── execution_plan/           <- SQL Server XML plan parser + analyzer
│   │   ├── parser.py             <- parse_execution_plan() -> ExecutionPlanNode tree
│   │   └── analyzer.py           <- analyze_plan() -> PlanAnalysis (bottlenecks etc)
│   ├── audit/                    <- User action audit trail
│   │   ├── logger.py             <- log_action() -> audit_logs table
│   │   └── repository.py         <- get_audit_logs(), count_audit_logs()
│   ├── notifications/            <- Slack / Teams webhook alerts
│   │   └── webhooks.py           <- send_notifications()
│   ├── scheduler/                <- PostgreSQL-backed scheduled scans
│   │   └── engine.py             <- add_task(), run_due_tasks(), parse_next_run()
│   ├── api/
│   │   ├── main.py               <- create_app() factory + start_api() CLI entry
│   │   ├── auth.py               <- init_auth(key) — call once at startup
│   │   ├── auth_rbac.py          <- JWT RBAC: create_access_token, make_rbac_dependency
│   │   ├── schemas.py            <- ALL Pydantic request/response models live here
│   │   └── routes/
│   │       ├── databases.py      <- /databases  (CRUD for db_registry)
│   │       ├── runs.py           <- /runs       (list, trigger, job poll, health-gate)
│   │       ├── findings.py       <- /findings   (list, filter, status update)
│   │       ├── trend.py          <- /trend      (time-series per database)
│   │       ├── reports.py        <- /reports    (download + CI/CD health-gate)
│   │       └── auth.py           <- /auth/token, /auth/me
│   ├── db/
│   │   ├── schema.sql            <- PostgreSQL schema — source of truth (13 tables)
│   │   ├── models.py             <- @dataclass: Run, Finding, DbRegistry, HealthTrend
│   │   ├── repository.py         <- all SQL (psycopg2, no ORM)
│   │   └── connection.py         <- init_pool / close_pool / create_schema
│   ├── engine/
│   │   ├── analyser.py           <- run_analysis() — main pipeline entry point
│   │   ├── scanner.py            <- load_objects() — file + live-DB SQL object loader
│   │   ├── dmv.py                <- DMV / live-DB performance checks
│   │   └── rules/
│   │       ├── base.py           <- BaseRule ABC, RuleFinding, SQLObject — DO NOT MODIFY
│   │       ├── __init__.py       <- ALL_RULES + build_rule_set(cfg)
│   │       ├── security.py       <- SEC001-005
│   │       ├── reliability.py    <- REL001-004
│   │       ├── performance.py    <- PERF001-008
│   │       ├── data_safety.py    <- DS001-006
│   │       ├── best_practices.py <- BP001-005
│   │       ├── parameter_sniffing.py <- PS001-004
│   │       ├── maintainability.py    <- MNT001-006
│   │       ├── dangerous_sql.py      <- DNG001-006
│   │       ├── custom.py             <- YamlRule, load_custom_rules()
│   │       └── compliance/
│   │           ├── __init__.py   <- get_compliance_rules(packs) registry
│   │           ├── sox.py        <- SOX001-006
│   │           ├── gdpr.py       <- GDPR001-006
│   │           └── rbi.py        <- RBI001-006
│   └── reports/
│       ├── excel.py / html.py / csv_report.py / json_report.py
└── tests/
    ├── fixtures/
    │   ├── good_proc.sql            <- must always produce 0 Critical/High findings
    │   ├── bad_proc.sql             <- must always produce >= 5 findings
    │   └── sample_table.sql
    ├── test_rules.py                <- SEC, PERF, REL, BP, DS, MNT, PS rules
    ├── test_dangerous_sql.py        <- DNG001-006
    ├── test_compliance.py           <- SOX/GDPR/RBI + registry + build_rule_set()
    ├── test_scanner.py              <- scanner unit tests
    ├── test_custom_rules.py         <- YAML custom rules (27 tests)
    ├── test_webhooks.py             <- Slack/Teams webhook notifications (19 tests)
    ├── test_scheduler.py            <- scheduled task engine (10 tests)
    ├── test_schema_intel.py         <- schema intelligence layer (34 tests)
    ├── test_ai_optimizer.py         <- AI optimizer mocked tests (21 tests)
    └── test_execution_plan.py       <- XML plan parser + analyzer (30 tests)
```

---

## Complete rule inventory

| File | Rule IDs | Count | Category string |
|------|----------|-------|-----------------|
| security.py | SEC001–005 | 5 | Security |
| reliability.py | REL001–004 | 4 | Reliability |
| performance.py | PERF001–008 | 8 | Performance |
| data_safety.py | DS001–006 | 6 | Data Safety |
| best_practices.py | BP001–005 | 5 | Best Practices |
| parameter_sniffing.py | PS001–004 | 4 | Performance |
| maintainability.py | MNT001–006 | 6 | Maintainability |
| dangerous_sql.py | DNG001–006 | 6 | Data Safety / Reliability / Best Practices |
| compliance/sox.py | SOX001–006 | 6 | Compliance-SOX |
| compliance/gdpr.py | GDPR001–006 | 6 | Compliance-GDPR |
| compliance/rbi.py | RBI001–006 | 6 | Compliance-RBI |
| **Total** | | **62** | |

**Next available IDs**: DNG007, SOX007, GDPR007, RBI007, or new category XXX001.

---

## CLI commands (14 total)

```
# Core analysis
dbanalyser run               # analyse SQL objects (file / live-DB / named DB / all DBs)
dbanalyser report            # generate report from stored PostgreSQL run
dbanalyser diff A B          # compare two run IDs (new / resolved findings)
dbanalyser history           # list previous runs
dbanalyser validate          # test SQL Server + PostgreSQL connections
dbanalyser init-db           # create / migrate PostgreSQL schema

# API
dbanalyser api               # start FastAPI server on :8000

# Database registry
dbanalyser db list           # show all registered databases
dbanalyser db add NAME       # add / update a database entry
dbanalyser db remove NAME    # soft-delete (deactivate) a database
dbanalyser db show NAME      # details + last 5 runs for one database
dbanalyser db sync           # push analysis_config.yaml databases into PostgreSQL

# Compliance
dbanalyser compliance-report # compliance-only Excel/JSON/CSV export (SOX/GDPR/RBI/DNG)

# Scheduling
dbanalyser schedule list     # list all scheduled tasks
dbanalyser schedule add DB   # add a scheduled scan
dbanalyser schedule remove   # remove a scheduled task
dbanalyser schedule run-due  # execute overdue tasks (run from Task Scheduler)

# Auth
dbanalyser auth hash-password  # generate bcrypt hash for config auth.users

# AI Intelligence (Phase E)
dbanalyser ingest            # ingest schema into vector knowledge base
                             #   --db LTFS_DEV     (from live SQL Server)
                             #   --files ./scripts  (from .sql files)
                             #   --use-transformers (sentence-transformers embeddings)
dbanalyser optimize NAME     # AI-optimize a SQL object via Anthropic Claude
                             #   --sql-file proc.sql
                             #   --execution-plan plan.xml
                             #   --model claude-sonnet-4-6
dbanalyser audit             # view audit log (action history)
                             #   --username alice
                             #   --action optimize
                             #   --limit 50
```

## API endpoints

| Prefix | Routes |
|--------|--------|
| `/databases` | GET `/`, GET `/summary`, GET `/{name}`, POST `/`, DELETE `/{name}` |
| `/runs` | GET `/`, GET `/{run_id}`, GET `/jobs/{job_id}`, POST `/trigger` |
| `/findings` | GET `/run/{run_id}`, GET `/summary/{run_id}`, PATCH `/{finding_id}/status` |
| `/trend` | GET `/all`, GET `/{db_name}` |
| `/reports` | GET `/download/{run_id}?fmt=excel\|html\|json\|csv`, GET `/health-gate/{run_id}` |
| `/health` | GET (no auth) |
| `/` | GET (no auth) |
| `/docs` | Swagger UI (no auth — Phase B task to lock this down) |

---

## Settings model — complete field list

All fields live in `dbanalyser/config.py → Settings`:

| Field | Type | Purpose |
|-------|------|---------|
| `source` | `SourceConfig` | Primary data source (file path / live-DB DSN) |
| `scope` | `ScopeConfig` | Object type filter, schema include/exclude |
| `analysis` | `AnalysisConfig` | Category on/off toggles, extended checks |
| `severity` | `SeverityConfig` | Minimum severity to report |
| `performance` | `PerformanceConfig` | Thread count, line limits, timeouts |
| `live_db` | `LiveDbConfig` | DMV settings, top-N slow queries |
| `output` | `OutputConfig` | Output dir, formats, snippet length |
| `postgres` | `PostgresConfig` | Host, port, database, user, password, **db_schema**, pool sizes |
| `versioning` | `VersioningConfig` | Hash-based drift detection |
| `run` | `RunModeConfig` | Workers, environment label, log level |
| `compliance` | `ComplianceConfig` | enabled_packs list + per-pack overrides |
| `api` | `ApiConfig` | api_key, host, port, reload |
| `notifications` | `NotificationsConfig` | Slack/Teams webhook URLs, thresholds |
| `custom_rules` | `CustomRulesConfig` | YAML rule directory and file paths |
| `scheduler` | `SchedulerConfig` | enabled flag, check_interval_sec |
| `auth` | `AuthConfig` | JWT secret, algorithm, token TTL, users list |
| `ai_optimizer` | `AIOptimizerConfig` | api_key, model, max_tokens, temperature, persist_results |
| `databases` | `List[DatabaseEntry]` | Multi-DB registry (synced to PostgreSQL) |
| `run_id` | `str` | Auto-generated timestamp (set by model_validator) |
| `timestamp` | `str` | Same as run_id |

**AIOptimizerConfig** fields (new in Phase E):

| Field | Default | Purpose |
|-------|---------|---------|
| `enabled` | `false` | Enable AI optimization features |
| `api_key` | `""` | Anthropic API key (prefer `ANTHROPIC_API_KEY` env var) |
| `model` | `claude-3-5-haiku-20241022` | Claude model ID |
| `max_tokens` | `4096` | Max response tokens |
| `temperature` | `0.1` | Low = deterministic SQL output |
| `include_schema` | `true` | Always include schema context (never disable) |
| `include_execution_plan` | `true` | Include plan when provided |
| `persist_results` | `true` | Save to `ai_optimizations` table |

---

## Non-negotiable rules

### Rule engine

```
# ALWAYS — analyser.py
effective_rules = build_rule_set(cfg)   # includes compliance packs
# NEVER
effective_rules = ALL_RULES             # silently skips compliance packs
```

- Every rule class: `rule_id` (e.g. `"DNG001"`), `category` (string), `analyse(obj) -> List[RuleFinding]`
- Every rule file: exports `<CATEGORY>_RULES: List[BaseRule] = [RuleClass(), ...]` at the bottom
- After adding a rule file: import its list in `engine/rules/__init__.py`, append to `ALL_RULES`
- `base.py` is the contract — never modify it without updating every rule and every test

### `_safe_source` vs raw `obj.source`

| Use `self._safe_source(obj)` | Use `obj.source` raw |
|------------------------------|----------------------|
| Most patterns (default) | LIKE `'%value%'` patterns |
| Keyword presence checks | EXECUTE('literal' + @var) concat patterns |
| DML patterns (UPDATE, DELETE) | Credential literal detection |
| Anything that might match inside a string comment | Hardcoded email / phone detection |

**Rule**: if your regex contains `N?'` or needs to see the content of a string literal, use `obj.source`. Everything else uses `_safe_source`.

### Severity scale

| Severity | Use when |
|----------|----------|
| Critical | Security exploit, data loss, OS command execution |
| High | Correctness bug, compliance breach, transaction integrity risk |
| Medium | Performance anti-pattern, bad practice, maintainability issue |
| Low | Style, minor improvement |

### Config

- New config section = new Pydantic model class + field in `Settings` + YAML block in `analysis_config.yaml`
- Backward-compatible YAML key aliases go in `@model_validator(mode="before")` in the model
- **`cfg.postgres.db_schema`** — NOT `.schema` (renamed to avoid shadowing `BaseModel.schema`)
  - The YAML key `schema:` still works via the `_aliases` validator
  - `connection.py` uses `cfg.db_schema` — keep in sync if you ever change this

### API

- All routes must have `dependencies=[AuthDep]` — never omit
- All request/response models live in `api/schemas.py` — never define inline Pydantic models in route files
- `api/main.py` `create_app()` is the uvicorn factory — `start_api()` is the CLI path
- `_JOBS` dict in `runs.py` is in-process only — flagged for Phase B replacement with a PostgreSQL jobs table

### Database

- All SQL is in `db/repository.py` — no raw SQL in routes, CLI, or analyser
- Schema changes: `schema.sql` first → `db/models.py` → `repository.py`
- `insert_run(run)` returns `int` (BIGSERIAL PK) — use this integer as FK in:
  - `bulk_insert_findings(run_int_id, findings)`
  - `upsert_health_trend(HealthTrend(run_id=run_int_id, ...))`
  - Never pass the UUID string `run.run_id` where an integer FK is expected

### Testing

- Write tests alongside every new rule — same session, not later
- Test file mirrors source: `engine/rules/dangerous_sql.py` → `tests/test_dangerous_sql.py`
- Minimum per rule: one positive detection test + one no-false-positive test
- Run before finishing any task: `python -m pytest tests/ -v --tb=short`
- **`good_proc.sql` invariant**: must always produce **0 Critical/High findings**
  - If a new rule breaks this, fix the fixture (add the correct SQL, e.g. `SET XACT_ABORT ON`) — do NOT weaken the rule
- **`bad_proc.sql` invariant**: must always produce **>= 5 findings**
- **Current count: 246 tests, 0 failures, 0 warnings** (as of Phase E)
- Full install health check: `python health_check.py` — must stay 14/14 PASS

**Test file inventory:**

| File | Tests | Covers |
|------|-------|--------|
| test_rules.py | 56 | SEC, PERF, REL, BP, DS, MNT, PS rules |
| test_dangerous_sql.py | 19 | DNG001-006 |
| test_compliance.py | 18 | SOX/GDPR/RBI + build_rule_set() |
| test_scanner.py | 14 | file + live-DB scanner |
| test_custom_rules.py | 27 | YAML custom rules engine |
| test_webhooks.py | 19 | Slack/Teams webhook payloads |
| test_scheduler.py | 10 | parse_next_run(), add/list/remove tasks |
| test_schema_intel.py | 34 | embedder, extractor, searcher |
| test_ai_optimizer.py | 21 | context_builder, optimizer (mocked API) |
| test_execution_plan.py | 30 | XML plan parser, bottleneck analyzer |
| **Total** | **246** | |

---

## How to add a new base rule category

1. Create `dbanalyser/engine/rules/<category>.py`
2. Import `BaseRule, RuleFinding, SQLObject` from `.base`
3. Define rule classes — `rule_id`, `category`, `analyse(obj)`
4. Export `<CATEGORY>_RULES: List[BaseRule] = [...]` at the bottom
5. In `engine/rules/__init__.py`: import the list, append to `ALL_RULES`
6. Add boolean toggle to `AnalysisCategoryConfig` in `config.py`
7. Add toggle to `analysis_config.yaml` under `analysis.categories:`
8. Create `tests/test_<category>.py` with full coverage

## How to add a compliance pack

1. Create `dbanalyser/engine/rules/compliance/<pack>.py`
2. Rule IDs follow `PACKXXX` pattern (e.g. HIPAA001)
3. Export `<PACK>_RULES: List[BaseRule] = [...]` at bottom
4. Register in `compliance/__init__.py → _PACK_REGISTRY`
5. Add tests in `tests/test_compliance.py`
6. Document in `analysis_config.yaml` under `compliance.enabled_packs:`

---

## Documented gotchas (found in production)

### 1. Keyword boundaries in compliance rules — NO `\b`
`_FINANCIAL_KEYWORDS` in `sox.py` and `_RBI_SENSITIVE_RE` in `rbi.py` intentionally have
**no `\b` word boundaries**. This lets them match CamelCase names like `AccountLedger`,
`usp_PostPayment`, `BankAccountDetails`. Do not add `\b` back — it silently breaks detection.

### 2. Audit table patterns — always include schema prefix group
Always use `(?:\[?\w+\]?\.)?` before table name patterns to handle both
`LedgerAudit` and `dbo.LedgerAudit`. Without it, schema-qualified inserts
to audit tables are not recognised as audit writes (false positive).

```python
# Correct
r'\bINSERT\s+INTO\s+(?:\[?\w+\]?\.)?\[?\w*audit\w*\]?\b'
# Wrong — misses dbo.LedgerAudit
r'\bINSERT\s+INTO\s+\w*audit\w*\b'
```

### 3. EXEC pattern in triggers — closing bracket must be optional
```python
# Correct — matches both dbo.usp_Proc and [dbo].[usp_Proc]
r'\b(EXEC|EXECUTE)\s+...(?:\[?\w+\]?\.)*\[?\w+\]?\b'
# Wrong — requires ] and misses unbracketed names
r'\b(EXEC|EXECUTE)\s+...(?:\[?\w+\]?\.)*\[?\w+\]\s*'
```

### 4. Recursive trigger DML pattern — unbracketed schema
```python
# Correct — matches UPDATE DBO.ORDERS and UPDATE [dbo].[Orders]
rf'\b(UPDATE|...)\s+(?:\[?\w+\]?\.)?{table_name}\b'
# Wrong — requires brackets around schema, misses DBO.ORDERS
rf'\b(UPDATE|...)\s+(?:\[\w+\]\.)?\[?{table_name}\]?\b'
```

### 5. `cfg.postgres.db_schema` not `.schema`
The field was renamed from `schema` to `db_schema` to avoid shadowing Pydantic's
`BaseModel.schema` method (which caused a runtime UserWarning and potential confusion).
The YAML key `schema:` still works via alias. `db/connection.py` uses `cfg.db_schema`.
Do not revert this rename.

### 6. `insert_run()` returns `int`, not `None`
Returns the BIGSERIAL integer PK via `RETURNING id`. This integer is the FK used in
`bulk_insert_findings` and `upsert_health_trend`. The UUID string `run.run_id` is a
separate field for human-readable identification — never use it as a database FK.

### 7. `build_rule_set(cfg)` vs `ALL_RULES`
`analyser.py` must always call `build_rule_set(cfg)` so compliance packs
are included when `cfg.compliance.enabled_packs` is non-empty.
Using `ALL_RULES` directly will silently skip all 18 compliance rules
even when they are correctly enabled in the YAML config.

### 8. Background job state is ephemeral
`_JOBS` dict in `api/routes/runs.py` lives in process memory only.
It is lost on server restart. This is acceptable for local/dev use.
For production: replace with a PostgreSQL `jobs` table (Phase B).

---

## AI Optimization — STRICT ENFORCEMENT RULES

These rules are enforced in `ai_optimizer/optimizer.py` and `ai_optimizer/context_builder.py`.
**NEVER violate them.**

### Rule 1 — Always fetch schema before optimization
```python
# CORRECT
ctx = build_optimization_context(object_name, sql, db_registry_id=id)
result = optimize_sql_object(..., schema_context=ctx["schema_context"])

# WRONG — will log a CLAUDE.md VIOLATION warning and degrade quality
result = optimize_sql_object(..., schema_context="")
```
`schema_context` must be obtained from `build_schema_context_for_object()` via
`build_optimization_context()`. **Never pass an empty string.**

### Rule 2 — Always include execution plan when available
```python
# CORRECT
ctx = build_optimization_context(..., execution_plan=plan_xml)

# WRONG — misses actual bottlenecks
ctx = build_optimization_context(...)  # omits execution_plan
```
If the user has a SQL Server execution plan (XML from `SET STATISTICS XML ON` or
SSMS estimated plan), it **must** be included. Without it, Claude only analyses
structure, not actual query costs.

### Rule 3 — Log context used for every AI call
All calls to `optimize_sql_object(persist=True)` are persisted to `ai_optimizations`
table with:
- `schema_context_used` — the exact schema context sent to Claude
- `execution_plan_used` — the exact plan text sent (or "" if none)
- `findings_used` — JSON array of findings passed to Claude
- `model_used` / `tokens_used` / `confidence_score`

**Never call `optimize_sql_object(persist=False)` in production flows.**
`persist=False` is only for tests.

### Rule 4 — Context quality gate
Before calling Claude, check `ctx["context_quality"]`:
- `"good"` — schema + plan + findings all present: proceed
- `"partial"` — proceed with warning to user
- `"none"` — warn user strongly; log and decline if schema_context is literally empty

### Schema Intelligence package
- `schema_intel/embedder.py` — TF-IDF 256-dim vectors (pure Python, no external deps)
  - Optional: sentence-transformers `all-MiniLM-L6-v2` (384-dim) via `use_transformers=True`
- `schema_intel/extractor.py` — extract from live SQL Server or file-based SQLObjects
- `schema_intel/repository.py` — `upsert_schema_object`, `get_embeddings_for_db`
- `schema_intel/searcher.py` — `search_schema`, `build_schema_context_for_object`
- All schema data stored in `schema_objects` PostgreSQL table (see `db/schema.sql`)

### AI Optimizer package
- `ai_optimizer/optimizer.py` — `optimize_sql_object()` — calls Anthropic API
- `ai_optimizer/context_builder.py` — `build_optimization_context()` — assembles all context
- Default model: `claude-3-5-haiku-20241022` (configurable in `ai_optimizer` config section)
- Results persisted to `ai_optimizations` PostgreSQL table

### Execution Plan package
- `execution_plan/parser.py` — `parse_execution_plan(xml_text)` → `ExecutionPlanNode` tree
- `execution_plan/analyzer.py` — `analyze_plan(xml|node)` → `PlanAnalysis`
- `PlanAnalysis` exposes: bottlenecks, table_scans, implicit_converts, sort_operators, spill_warnings

### Audit package
- `audit/logger.py` — `log_action(username, action, resource_type, resource_id, details)`
- `audit/repository.py` — `get_audit_logs(username, action, resource_type, limit)`
- All records in `audit_logs` PostgreSQL table

---

## Settings model additions (Phase E)

| Field | Type | Purpose |
|-------|------|---------|
| `notifications` | `NotificationsConfig` | Webhook alerts (Slack/Teams) |
| `custom_rules` | `CustomRulesConfig` | YAML-driven custom rules |
| `scheduler` | `SchedulerConfig` | Scheduled scan engine |
| `auth` | `AuthConfig` | JWT RBAC for API |
| `ai_optimizer` | `AIOptimizerConfig` | Anthropic Claude settings |

---

## CLI commands (Phase E additions)

```
dbanalyser ingest         # Ingest schema from live DB or files → schema_objects table
dbanalyser optimize NAME  # AI-optimize a SQL object via Claude
dbanalyser audit          # View audit log
dbanalyser schedule list  # List scheduled tasks
dbanalyser schedule add   # Add a scheduled scan task
dbanalyser schedule remove # Remove a scheduled task
dbanalyser schedule run-due # Execute overdue tasks
dbanalyser auth hash-password # Generate bcrypt password hash
dbanalyser compliance-report  # Generate compliance-only Excel/JSON/CSV report
```

---

## New PostgreSQL tables (Phase E)

| Table | Purpose |
|-------|---------|
| `schema_objects` | Vector knowledge base for schema intelligence |
| `ai_optimizations` | Audit trail of every AI optimization call |
| `audit_logs` | User action history |
| `pipeline_steps` | Per-run step-level observability |

All tables defined in `dbanalyser/db/schema.sql` (safe to re-run).

---

## Pending work (as of current session)

### Phase B — Production hardening ✅
- [x] `Dockerfile` + `docker-compose.yml` (API + PostgreSQL + Dashboard)
- [ ] Rate limiting + `/v1/` API versioning prefix
- [x] Replace `_JOBS` in-process dict with PostgreSQL jobs table
- [ ] Lock down `/docs` Swagger UI behind API key when auth is enabled
- [ ] Structured JSON logging with `run_id` correlation field

### Phase C — Compliance & dashboard UX ✅
- [x] Compliance dashboard page in Streamlit (SOX / GDPR / RBI scorecard tabs)
- [x] "Dangerous DML" highlight card on existing findings page
- [x] `dbanalyser compliance-report` CLI command (compliance-only Excel/JSON/CSV export)
- [x] Extend health-gate: `?max_sox=0&max_gdpr=2` per-pack thresholds

### Phase D — Enterprise features ✅
- [x] User auth / RBAC (JWT + bcrypt, roles: viewer/analyst/admin)
- [x] Scheduled scans (daily/weekly/hourly/manual via `dbanalyser schedule`)
- [x] Object-level source-hash drift detection across runs (`detect_and_mark_content_drift`)
- [x] Custom rules via YAML definition (no-code rule authoring)
- [x] Slack / Teams webhook alerts on Critical threshold breach

### Phase E — AI Intelligence layer ✅
- [x] Schema Intelligence: `schema_intel/` package (embedder, extractor, repository, searcher)
- [x] AI Optimizer: `ai_optimizer/` package (optimizer, context_builder)
- [x] Execution Plan: `execution_plan/` package (parser, analyzer)
- [x] Audit: `audit/` package (logger, repository)
- [x] New DB tables: schema_objects, ai_optimizations, audit_logs, pipeline_steps
- [x] Config: `AIOptimizerConfig` in `Settings`
- [x] Dashboard: AI Optimizer, Schema Explorer, Execution Plans, Findings Intelligence, Settings, Audit Logs, Pipeline View, Ingestion Status pages
- [x] CLI: `dbanalyser ingest`, `dbanalyser optimize`, `dbanalyser audit`
- [x] CLAUDE.md: AI enforcement rules
- [x] Tests: test_schema_intel.py (42), test_ai_optimizer.py (21), test_execution_plan.py (30)

### Phase F — API + Intelligence routes ✅
- [x] API routes: `GET/POST /schema/`, `POST /ai/optimize`, `GET /ai/optimizations`, `GET /audit/`, `GET /pipeline/{run_id}`
- [x] Findings deduplication across runs: `enrich_findings_with_history()` — suppresses repeated same-object/same-rule findings
- [x] Object-level source-hash drift detection: `detect_and_mark_content_drift()` — marks changed objects in `object_snapshots`
- [x] Tests: test_api_schema.py (14), test_api_ai.py (9), test_api_audit_pipeline.py (11), test_drift_dedup.py (14)
- [x] Total: **260 tests, 0 failures**

---

## SaaS Transformation Roadmap (Phase G onwards)

**Goal**: Transform DBAnalyser from a single-tenant tool into a multi-client, multi-database,
multi-user enterprise SaaS platform where each client organisation manages its own databases,
users, assessment configurations, and schedules — and generates PDF reports.

---

### Phase G — Multi-Tenancy Foundation  ← NEXT

**Goal**: Add organisation-level isolation so every table is tenant-scoped.

#### G1 — Database schema changes (`db/schema.sql`)
- New table: `organizations` (id, name, slug, plan, is_active, created_at, updated_at)
- New table: `users` (id, org_id FK, username, email, password_hash, role, is_active, created_at)
- Add `org_id INTEGER REFERENCES organizations(id)` to: `db_registry`, `runs`, `findings`, `dmv_snapshots`, `health_trend`, `schema_objects`, `ai_optimizations`, `audit_logs`, `scheduled_tasks`, `jobs`
- Drop UNIQUE constraint on `db_registry.name`, replace with UNIQUE(org_id, name)
- New table: `assessment_configs` — per-database rule overrides (db_registry_id, config_json)
- New table: `invitations` — pending user invites (org_id, email, role, token, expires_at)

#### G2 — Auth upgrade
- Move users from `analysis_config.yaml` to `users` PostgreSQL table
- JWT payload adds: `org_id`, `user_id`, `email` alongside existing `role`
- All API routes filter by `org_id` from token — never trust client-supplied org_id
- New endpoints: `POST /auth/register` (org creation + first admin), `POST /auth/login`, `GET /auth/me`

#### G3 — Tenant-aware repository layer
- All `db/repository.py` queries gain `org_id` parameter, added to every WHERE clause
- `get_cursor()` context manager unchanged — filtering is at query level (not RLS)
- New: `org_repository.py` — CRUD for organizations, users, invitations

#### G4 — Config/connection store
- SQL Server connection strings stored encrypted in `db_registry` (use Fernet symmetric encryption)
- Remove dependency on `analysis_config.yaml` for database entries — all from PostgreSQL
- `analysis_config.yaml` becomes system defaults only (no client databases)

**Deliverables**: Fully isolated data per org, JWT-based org scoping, users in DB not YAML

---

### Phase H — Self-Service Portal (Streamlit)

**Goal**: End users manage everything from the UI — no YAML editing, no CLI required.

#### H1 — Authentication screens
- Login page (replaces current direct access)
- Organisation registration wizard (step 1: org name → step 2: admin user → step 3: first database)
- Forgot password / token-based reset via email

#### H2 — Database Management UI
- **Add Database** form: name, host, port, DB name, auth type (Windows/SQL), test connection button
- **Edit / Remove** database with confirmation
- **Connection test** — live pyodbc connect test from form, green/red status
- Database list with last scan date, health score, status badge
- All changes go to `db_registry` (org-scoped), not YAML

#### H3 — Assessment Configuration UI (per database)
- Rule toggle panel: enable/disable any of 62 rules per database
- Threshold overrides: max procedure lines, nesting depth, slow query threshold
- Compliance pack selection: SOX / GDPR / RBI checkboxes per database
- Severity sensitivity: minimum severity to report (Critical only / High+ / Medium+ / All)
- Config stored in `assessment_configs` table as JSONB, merged with global defaults at run time

#### H4 — User Management UI (admin only)
- User list with role badges (viewer / analyst / admin)
- Invite user by email (generates invitation token, displays link)
- Change role / deactivate user
- My Profile page (change password, notification preferences)

**Deliverables**: Full self-service, no YAML required for any client operation

---

### Phase I — Schedule Management (Self-Service)

**Goal**: Clients configure scan schedules from the UI and get notified on completion.

#### I1 — Schedule UI (upgrade existing Schedule Manager page)
- Per-database schedule card: set frequency (manual / hourly / daily@time / weekly@day@time)
- Toggle DMV analysis on/off per scheduled run
- Select report formats for auto-generation (Excel, PDF, JSON)
- Enable/disable schedule without deleting it
- Next run countdown + last run status

#### I2 — Scheduler engine upgrade
- `scheduled_tasks` gains `org_id` — tasks scoped to organisation
- Add `notify_email` TEXT column — send report link on completion
- Add `report_formats` JSONB — formats to auto-generate post-scan
- `run_due_tasks()` resolves org context before running, applies org's assessment_config

#### I3 — Email notifications
- Send email on: scan complete (with health score), scan failed, new Critical findings
- Simple SMTP (configurable host/port/from in system config)
- Email template: HTML with health score, top 5 findings, link to dashboard
- Per-user notification preferences (opt-in/out per event type)

**Deliverables**: Fully self-service scheduling with email alerts

---

### Phase J — PDF Report Generation

**Goal**: Comprehensive, branded PDF reports downloadable from the dashboard.

#### J1 — PDF engine (`reports/pdf.py`)
- Library: `reportlab` (robust, no browser dependency)
- Page sections:
  1. Cover page — org name, database, run date, health score badge, environment
  2. Executive Summary — health trend sparkline, finding counts by severity, top 3 risks
  3. Finding Details — table per severity: rule ID, object, issue, recommendation
  4. Compliance Scorecard — SOX/GDPR/RBI pass/fail per rule (if enabled)
  5. DMV Performance — top slow queries, missing indexes, table sizes (if available)
  6. Trend Chart — last 10 runs health score line chart (matplotlib → embedded image)
  7. Appendix — full object inventory with risk scores

#### J2 — Chart embedding
- Use `plotly` → `kaleido` for PNG chart exports embedded in PDF
- Charts: health trend, severity distribution pie, top 10 tables by size, missing index impact

#### J3 — Dashboard integration
- **Download Report** button on Run History and individual run pages
- Format selector: Excel / PDF / JSON / CSV / HTML
- PDF auto-generated and streamed as download
- Auto-generated post-scan when schedule includes PDF in formats list

#### J4 — API endpoint
- `GET /reports/download/{run_id}?fmt=pdf` — streams PDF
- `GET /reports/download/{run_id}?fmt=pdf&sections=executive,compliance` — partial report

**Deliverables**: Publication-quality PDF reports, downloadable on demand or auto-generated

---

### Phase K — SaaS Infrastructure & Admin Portal

**Goal**: System-level operations, usage tracking, and multi-tenant governance.

#### K1 — Super-admin portal (separate Streamlit page, admin role only)
- Organisation list: name, user count, DB count, last activity, plan tier
- Impersonate org (read-only view as any tenant)
- Suspend / reactivate organisation
- Global usage metrics: total scans, total findings, active users (last 30 days)

#### K2 — Usage & billing hooks
- `usage_metrics` table: org_id, month, scan_count, object_count, ai_calls, report_downloads
- Recorded automatically at end of each scan and AI optimization
- Usage dashboard tab in super-admin portal
- Pluggable billing hook (emit usage event — integrate Stripe/Paddle externally)

#### K3 — API hardening
- Rate limiting per org (e.g., 100 scans/day on free tier)
- `/v1/` prefix for all API routes
- Lock down `/docs` Swagger UI behind admin API key
- Structured JSON logging with `org_id` + `run_id` correlation

#### K4 — Tenant provisioning
- One-command org setup: `dbanalyser org create "ACME Corp"` → creates org + admin invite
- Tenant offboarding: `dbanalyser org deactivate ACME` → soft-deletes all data

**Deliverables**: Multi-tenant governance, usage tracking, production-ready API

---

## Phase dependency order

```
G (Multi-tenancy Foundation)
  └── H (Self-Service Portal)
        └── I (Schedule Management)
  └── J (PDF Reports)          ← can start in parallel with H
  └── K (SaaS Infrastructure)  ← starts after G, runs alongside H/I/J
```

---

## Live Environment (as of 2026-04-01)

### PostgreSQL — dbanalyser database
- Host: localhost:5432, database: dbanalyser, user: postgres, password: sa
- Tables populated: db_registry (1 DB: LTFS_DEV), runs (run_id=7 is latest), findings (25), object_snapshots (16), health_trend, dmv_snapshots (10 rows), schema_objects (1,531)

### dmv_snapshots (run_id=7) — imported from Onex_QueryDetails.xlsx
| dmv_type | rows |
|----------|------|
| db_info | 12 |
| sql_agent_jobs | 40 |
| index_fragmentation | 211 |
| dmv_missing_indexes | 25 |
| dmv_index_usage | 50 |
| dmv_slow_queries | 37 |
| dmv_deadlocks | 1000 |
| dmv_table_sizes | 1571 |
| server_info | 3 |

### Schema objects (schema_objects table)
- 1,531 objects ingested from D:\LTFS (3,862 SQL files)
- db_registry_id=1 (LTFS_DEV)
- TF-IDF embeddings (256-dim, pure Python)

### Key known gotchas (found during live setup)
- `PostgresConfig` uses `.user` NOT `.username` — `connection.py` was broken with `.username`, fixed with replace_all
- `Styler.applymap()` → `Styler.map()` in Pandas 2.x (fixed in _page_all_databases and _page_run_history)
- NUL bytes (`\x00`) in SQL files must be stripped before PostgreSQL insert — fixed in schema_intel/repository.py
- `scan_files(root, include_schemas, include_types)` — NOT `scan_directory` — fixed in cli.py cmd_ingest
- `DataFrame.get("col","")` returns empty string if col missing, not a Series — `.fillna()` fails on string; use `col in df.columns` check first
- seed_db.py — seeds LTFS_DEV entry, runs (id=2 + 5 historical), 25 findings, health_trend
- import_xls.py — imports Onex_QueryDetails.xlsx sheets into dmv_snapshots for run_id=7

---

## Quick reference — common commands

```bash
# Verify installation (run first after any changes)
python health_check.py

# Run all tests
python -m pytest tests/ -v --tb=short

# Run specific test files
python -m pytest tests/test_schema_intel.py -v
python -m pytest tests/test_ai_optimizer.py -v
python -m pytest tests/test_execution_plan.py -v

# Run a specific test class
python -m pytest tests/test_dangerous_sql.py::TestMissingWhereOnUpdateRule -v

# Start API in dev mode
python -m dbanalyser api --reload --port 8000

# Direct uvicorn (same result)
uvicorn dbanalyser.api.main:app --reload --port 8000

# Analyse local SQL files
python -m dbanalyser run --config analysis_config.yaml

# Analyse a registered database
python -m dbanalyser run --db-name LTFS_DEV

# Analyse all active databases
python -m dbanalyser run --all-dbs

# Initialise PostgreSQL schema (all 13 tables including Phase E)
python -m dbanalyser init-db

# Sync databases from YAML into PostgreSQL registry
python -m dbanalyser db sync

# --- AI Intelligence workflow ---

# Step 1: Ingest schema from live SQL Server
python -m dbanalyser ingest --db LTFS_DEV

# Step 1b: Ingest from local SQL files
python -m dbanalyser ingest --files ./sql_scripts

# Step 2: Run analysis to get findings
python -m dbanalyser run --db-name LTFS_DEV

# Step 3: AI-optimize a procedure (schema + findings used automatically)
python -m dbanalyser optimize dbo.usp_ProcessPayment \
    --sql-file ./usp_ProcessPayment.sql \
    --execution-plan ./plan.xml

# View audit log
python -m dbanalyser audit --action optimize --limit 20

# --- Compliance ---

# Generate compliance report
python -m dbanalyser compliance-report --run-id <run_id> --format excel

# --- Scheduling ---

python -m dbanalyser schedule add LTFS_PROD --schedule "daily@02:00"
python -m dbanalyser schedule list
python -m dbanalyser schedule run-due

# --- Auth ---
python -m dbanalyser auth hash-password myS3cr3t
```
