# DBAnalyser — Test Cases Document
## Version 2.0.0 | LTFS Technology | March 2026

---

## Table of Contents

1. Test Strategy
2. Test Environment
3. Unit Test Cases — Rule Engine
4. Unit Test Cases — Dangerous SQL Rules
5. Unit Test Cases — Compliance Packs
6. Unit Test Cases — Scanner
7. Integration Test Cases — Analyser Pipeline
8. Integration Test Cases — Config Loader
9. API Test Cases
10. CLI Test Cases
11. Dashboard Test Cases
12. Regression Test Checklist
13. Test Execution Summary
14. Unit Test Cases — Custom Rules (test_custom_rules.py)
15. Unit Test Cases — Webhooks (test_webhooks.py)
16. Unit Test Cases — Scheduler (test_scheduler.py)

---

## 1. Test Strategy

### 1.1 Approach

DBAnalyser uses a multi-layer test strategy:

| Layer | Tool | Location | Count |
|-------|------|----------|-------|
| Unit — rules | pytest | `tests/test_rules.py`, `test_dangerous_sql.py`, `test_compliance.py` | 112 |
| Unit — scanner | pytest | `tests/test_scanner.py` | 14 |
| Unit — custom rules | pytest | `tests/test_custom_rules.py` | 27 |
| Unit — webhooks | pytest | `tests/test_webhooks.py` | 19 |
| Unit — scheduler | pytest | `tests/test_scheduler.py` | 10 |
| Integration — pipeline | pytest | `tests/test_rules.py::TestBadProcFixture` | 2 |
| Manual — API | curl / Swagger UI | `docs/Test_Cases.md` (this file) | Listed below |
| Manual — CLI | Terminal | `docs/Test_Cases.md` | Listed below |
| Manual — Dashboard | Browser | `docs/Test_Cases.md` | Listed below |

### 1.2 Pass criteria for automated tests

```bash
python -m pytest tests/ -v --tb=short
# Required: 168 passed, 0 failed, 0 warnings
```

### 1.3 Fixture invariants

| Fixture | Invariant |
|---------|-----------|
| `tests/fixtures/good_proc.sql` | Must produce **0 Critical or High findings** when ALL_RULES are applied |
| `tests/fixtures/bad_proc.sql` | Must produce **>= 5 findings** when ALL_RULES are applied |

---

## 2. Test Environment

### 2.1 Setup

```bash
cd D:\LTFS\ltfs-analyzer
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### 2.2 Run all automated tests

```bash
python -m pytest tests/ -v --tb=short
```

### 2.3 Run a specific test file

```bash
python -m pytest tests/test_dangerous_sql.py -v
python -m pytest tests/test_compliance.py -v
python -m pytest tests/test_scanner.py -v
```

---

## 3. Unit Test Cases — Rule Engine (test_rules.py)

### TC-SEC-001 — Dynamic SQL Injection detection

| Field | Value |
|-------|-------|
| **Test ID** | TC-SEC-001 |
| **Rule** | DynamicSqlInjectionRule (SEC001) |
| **Class** | TestDynamicSqlInjectionRule |

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_exec_variable` | `EXEC(@sql)` | ≥1 finding, severity=Critical | ✅ PASS |
| 2 | `test_detects_string_concat` | `EXECUTE('SELECT ' + @col)` | ≥1 finding | ✅ PASS |
| 3 | `test_sp_executesql_with_params_ok` | `EXEC sp_executesql @stmt, N'@id INT', @id=@CustomerId` | 0 findings | ✅ PASS |

---

### TC-SEC-002 — Hardcoded Credential detection

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_password_literal` | `SET @password = 'MySecret123'` | ≥1 finding | ✅ PASS |
| 2 | `test_no_false_positive` | `SELECT CustomerName FROM dbo.Customers` | 0 findings | ✅ PASS |

---

### TC-SEC-005 — xp_cmdshell detection

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_xp_cmdshell` | `EXEC xp_cmdshell 'dir C:\\'` | ≥1 finding, severity=Critical | ✅ PASS |

---

### TC-REL-001 — Missing TRY/CATCH

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_missing_try_catch` | SP with INSERT, no TRY/CATCH | 1 finding, severity=High | ✅ PASS |
| 2 | `test_passes_with_try_catch` | SP with BEGIN TRY / BEGIN CATCH | 0 findings | ✅ PASS |
| 3 | `test_skips_view` | View object | 0 findings | ✅ PASS |

---

### TC-REL-002 — Transaction Without Rollback

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_begin_tran_without_catch` | `BEGIN TRANSACTION; ... COMMIT;` (no CATCH) | 1 finding | ✅ PASS |
| 2 | `test_detects_catch_without_rollback` | TRY/CATCH block missing ROLLBACK | 1 finding, recommendation contains "ROLLBACK" | ✅ PASS |

---

### TC-PERF-001 — SELECT *

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_select_star` | `SELECT * FROM dbo.Orders` | ≥1 finding, severity=High | ✅ PASS |
| 2 | `test_no_false_positive_explicit_cols` | `SELECT OrderId, OrderDate FROM dbo.Orders` | 0 findings | ✅ PASS |

---

### TC-PERF-004 — NOLOCK hint

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_nolock` | `SELECT * FROM dbo.Orders WITH (NOLOCK)` | 1 finding | ✅ PASS |
| 2 | `test_no_nolock` | `SELECT * FROM dbo.Orders` | 0 findings | ✅ PASS |

---

### TC-PERF-005 — Non-sargable WHERE (leading wildcard)

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_leading_wildcard` | `WHERE Name LIKE '%Smith'` | ≥1 finding | ✅ PASS |
| 2 | `test_trailing_wildcard_ok` | `WHERE Name LIKE 'Smith%'` | 0 findings | ✅ PASS |

---

### TC-BP-002 — Missing ANSI_NULLS setting

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_missing` | SP without SET ANSI_NULLS | 1 finding | ✅ PASS |
| 2 | `test_passes_with_setting` | SP with `SET ANSI_NULLS ON` | 0 findings | ✅ PASS |

---

### TC-BP-003 — sp_ prefix on user stored procedures

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_sp_prefix` | name=`sp_GetOrders` | 1 finding | ✅ PASS |
| 2 | `test_usp_prefix_ok` | name=`usp_GetOrders` | 0 findings | ✅ PASS |

---

### TC-DS-001 — Implicit NULL comparison

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_equals_null` | `WHERE Col = NULL` | ≥1 finding | ✅ PASS |
| 2 | `test_is_null_ok` | `WHERE Col IS NULL` | 0 findings | ✅ PASS |

---

### TC-MNT-001 — Long procedure

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_long_proc` | 600-line SP | 1 finding | ✅ PASS |
| 2 | `test_short_proc_ok` | 3-line SP | 0 findings | ✅ PASS |

---

### TC-PS-002 — Optional parameter anti-pattern

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_or_null_pattern` | `WHERE (@Status IS NULL OR Status = @Status)` | ≥1 finding | ✅ PASS |
| 2 | `test_clean_sp_ok` | `WHERE Id = @Id` | 0 findings | ✅ PASS |

---

### TC-INT-001 — Bad procedure fixture (integration)

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_bad_proc_has_many_findings` | `tests/fixtures/bad_proc.sql` against ALL_RULES | ≥5 findings total | ✅ PASS |
| 2 | `test_good_proc_has_few_findings` | `tests/fixtures/good_proc.sql` against ALL_RULES | 0 Critical or High findings | ✅ PASS |

---

## 4. Unit Test Cases — Dangerous SQL Rules (test_dangerous_sql.py)

### TC-DNG001 — UPDATE without WHERE

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_update_without_where` | `UPDATE dbo.Orders SET Status = 1` | ≥1 finding, severity=High, issue contains "WHERE" | ✅ PASS |
| 2 | `test_update_statistics_ignored` | `UPDATE STATISTICS dbo.Orders` | 0 findings | ✅ PASS |
| 3 | `test_no_finding_with_where` | `UPDATE dbo.Orders SET Status=1 WHERE OrderId=@Id` | 0 findings | ✅ PASS |
| 4 | `test_no_finding_on_view` | View object | 0 findings | ✅ PASS |

---

### TC-DNG002 — DELETE without WHERE

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_delete_without_where` | `DELETE FROM dbo.StagingTable` | ≥1 finding, severity=High | ✅ PASS |
| 2 | `test_no_finding_with_where` | `DELETE FROM dbo.Orders WHERE OrderDate < '2000-01-01'` | 0 findings | ✅ PASS |
| 3 | `test_delete_shorthand_without_where` | `DELETE dbo.Logs` | ≥1 finding | ✅ PASS |

---

### TC-DNG003 — Missing XACT_ABORT

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_missing_xact_abort` | SP with BEGIN TRANSACTION, no SET XACT_ABORT ON | 1 finding, issue contains "XACT_ABORT" | ✅ PASS |
| 2 | `test_no_finding_when_set` | SP with SET XACT_ABORT ON + BEGIN TRANSACTION | 0 findings | ✅ PASS |
| 3 | `test_no_finding_without_transaction` | SP with no BEGIN TRANSACTION | 0 findings | ✅ PASS |
| 4 | `test_skips_view` | View object | 0 findings | ✅ PASS |

---

### TC-DNG004 — Trigger calling stored procedure

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_exec_in_trigger` | Trigger with `EXEC dbo.usp_SendNotification` | ≥1 finding, issue contains "stored procedure" | ✅ PASS |
| 2 | `test_no_finding_on_sp` | SP with EXEC | 0 findings (rule only fires on Trigger type) | ✅ PASS |
| 3 | `test_no_finding_for_sp_executesql` | Trigger with `EXEC sp_executesql @sql` | 0 findings (sp_executesql excluded) | ✅ PASS |

---

### TC-DNG005 — SELECT * in trigger

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_select_star_in_trigger` | Trigger with `SELECT * FROM inserted` | ≥1 finding, issue contains "SELECT *" | ✅ PASS |
| 2 | `test_no_finding_on_explicit_columns` | Trigger with `SELECT Id, Name FROM inserted` | 0 findings | ✅ PASS |
| 3 | `test_skips_stored_procedure` | SP with `SELECT * FROM dbo.T` | 0 findings (rule only fires on Trigger type) | ✅ PASS |

---

### TC-DNG006 — Recursive trigger risk

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_self_update` | Trigger ON dbo.Orders that UPDATE dbo.Orders in body | ≥1 finding, issue contains "recursion" | ✅ PASS |
| 2 | `test_no_finding_on_different_table` | Trigger ON dbo.Orders that INSERT INTO dbo.AuditLog | 0 findings | ✅ PASS |

---

## 5. Unit Test Cases — Compliance Packs (test_compliance.py)

### TC-SOX001 — Missing audit columns on financial table

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_financial_table_without_audit_cols` | Table named `Ledger` with no audit columns | 1 finding, issue contains "audit" | ✅ PASS |
| 2 | `test_no_finding_with_created_by` | Table with `CreatedBy` column | 0 findings | ✅ PASS |
| 3 | `test_skips_non_financial_table` | Table named `SystemLogs` | 0 findings | ✅ PASS |

---

### TC-SOX002 — DML without audit log

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_insert_without_audit_log` | Financial SP: INSERT with no audit table write | 1 finding | ✅ PASS |
| 2 | `test_no_finding_with_audit_insert` | Financial SP: INSERT + `INSERT INTO dbo.LedgerAudit` | 0 findings | ✅ PASS |

---

### TC-SOX003 — xp_cmdshell in financial object

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_xp_cmdshell_in_financial_sp` | Financial SP with `EXEC xp_cmdshell` | ≥1 finding, severity=Critical | ✅ PASS |

---

### TC-SOX004 — GRANT on financial table

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_grant_on_financial_table` | `GRANT SELECT ON dbo.AccountLedger TO [AppUser]` | ≥1 finding, issue contains "AccountLedger" | ✅ PASS |
| 2 | `test_no_finding_on_non_financial_table` | `GRANT SELECT ON dbo.UISettings TO [AppUser]` | 0 findings | ✅ PASS |

---

### TC-SOX005 — No error handling in financial transaction

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_missing_try_catch` | Financial SP with BEGIN TRANSACTION, no TRY/CATCH | 1 finding | ✅ PASS |
| 2 | `test_no_finding_with_try_catch` | Financial SP with full TRY/CATCH | 0 findings | ✅ PASS |

---

### TC-GDPR001 — SELECT * on PII object

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_select_star_on_pii_object` | `SELECT * FROM ... WHERE email IS NOT NULL` | ≥1 finding, issue contains "SELECT *" | ✅ PASS |
| 2 | `test_no_finding_when_no_pii_reference` | `SELECT * FROM dbo.Products` | 0 findings | ✅ PASS |
| 3 | `test_no_finding_with_explicit_columns` | `SELECT CustomerId, email FROM dbo.Customers` | 0 findings | ✅ PASS |

---

### TC-GDPR002 — PII in PRINT / RAISERROR

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_print_with_pii_column` | `PRINT 'Email: ' + email` | ≥1 finding, issue contains "PII" | ✅ PASS |
| 2 | `test_no_finding_without_pii` | `PRINT 'Processing complete'` | 0 findings | ✅ PASS |

---

### TC-GDPR003 — Unmasked PII return

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_view_returning_email_without_masking` | View with `SELECT email, phone` | 1 finding, recommendation contains "mask" | ✅ PASS |
| 2 | `test_no_finding_with_masking_function` | View with `HASHBYTES(..., email)` | 0 findings | ✅ PASS |

---

### TC-GDPR004 — Hardcoded personal data

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_hardcoded_email` | `VALUES ('john.doe@example.com')` | ≥1 finding, issue contains "email" | ✅ PASS |
| 2 | `test_no_finding_on_placeholder` | `WHERE Status = 'Active'` | 0 findings | ✅ PASS |

---

### TC-GDPR005 — Missing retention hint on PII table

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_pii_table_without_retention` | Table with `email`, `phone` columns, no retention comment | 1 finding | ✅ PASS |
| 2 | `test_no_finding_with_retention_comment` | Table with `-- GDPR: retain 6 years` comment | 0 findings | ✅ PASS |
| 3 | `test_skips_non_pii_table` | `CREATE TABLE dbo.Products (Id INT, Name NVARCHAR)` | 0 findings | ✅ PASS |

---

### TC-RBI001 — Unencrypted sensitive financial columns

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_unencrypted_account_no` | Table with `account_no NVARCHAR(20)`, no encryption | 1 finding, severity=Critical | ✅ PASS |
| 2 | `test_no_finding_with_encryption` | Table with ENCRYPTBYKEY comment | 0 findings | ✅ PASS |
| 3 | `test_skips_non_financial_table` | Table named `AppConfig` | 0 findings | ✅ PASS |

---

### TC-RBI002 — Missing transaction audit log

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_sp_without_audit_log` | SP named `usp_TransferFunds` with UPDATE, no audit | 1 finding, severity=Critical | ✅ PASS |
| 2 | `test_no_finding_with_audit_log` | SP with `INSERT INTO dbo.TransactionAudit` | 0 findings | ✅ PASS |

---

### TC-RBI005 — Missing ROLLBACK in financial SP

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_missing_rollback` | Financial SP with TRY/CATCH but no ROLLBACK | 1 finding, recommendation contains "ROLLBACK" | ✅ PASS |
| 2 | `test_no_finding_with_full_error_handling` | Financial SP with TRY/CATCH + ROLLBACK TRANSACTION | 0 findings | ✅ PASS |

---

### TC-RBI006 — Hardcoded connection string

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_hardcoded_connection_string` | SP with `'Data Source=prod-sql;Password=...'` | ≥1 finding, severity=High | ✅ PASS |
| 2 | `test_no_finding_on_clean_sp` | Normal SP with no connection string | 0 findings | ✅ PASS |

---

### TC-COMPLIANCE-REG — Pack registry

| # | Test Method | Expected | Status |
|---|-------------|----------|--------|
| 1 | `test_all_packs_registered` | COMPLIANCE_PACKS == {"sox", "gdpr", "rbi"} | ✅ PASS |
| 2 | `test_get_sox_rules` | Returns only SOX001–006 rules | ✅ PASS |
| 3 | `test_get_multiple_packs` | Returns GDPR + RBI rules, no SOX | ✅ PASS |
| 4 | `test_empty_packs_returns_empty` | Returns [] | ✅ PASS |
| 5 | `test_unknown_pack_skipped_gracefully` | Unknown pack silently ignored, SOX rules returned | ✅ PASS |

---

### TC-COMPLIANCE-BUILD — build_rule_set() integration

| # | Test Method | Expected | Status |
|---|-------------|----------|--------|
| 1 | `test_no_compliance_without_config` | build_rule_set(None) == list(ALL_RULES) | ✅ PASS |
| 2 | `test_compliance_rules_added_when_enabled` | SOX rules present, len > len(ALL_RULES) | ✅ PASS |
| 3 | `test_empty_packs_returns_base_rules_only` | len == len(ALL_RULES) | ✅ PASS |

---

## 6. Unit Test Cases — Scanner (test_scanner.py)

### TC-SCAN-001 — Object type detection from DDL

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_detects_stored_procedure` | DDL with `CREATE PROCEDURE` | obj_type = "Stored Procedure" | ✅ PASS |
| 2 | `test_detects_view` | DDL with `CREATE VIEW` | obj_type = "View" | ✅ PASS |
| 3 | `test_detects_trigger` | DDL with `CREATE TRIGGER` | obj_type = "Trigger" | ✅ PASS |
| 4 | `test_detects_table` | DDL with `CREATE TABLE` | obj_type = "Table" | ✅ PASS |
| 5 | `test_falls_back_to_filename` | DDL with no keyword, file = `Orders_sp.sql` | Falls back to filename-based type | ✅ PASS |

---

### TC-SCAN-002 — Object name extraction

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_extracts_schema_and_name` | `CREATE PROCEDURE dbo.usp_GetOrders` | schema="dbo", name="usp_GetOrders" | ✅ PASS |
| 2 | `test_defaults_to_dbo_schema` | `CREATE PROCEDURE usp_GetOrders` (no schema) | schema="dbo" | ✅ PASS |
| 3 | `test_falls_back_to_filename` | No CREATE statement | name derived from filename | ✅ PASS |

---

### TC-SCAN-003 — File scanning

| # | Test Method | Input | Expected | Status |
|---|-------------|-------|----------|--------|
| 1 | `test_scans_fixture_directory` | `tests/fixtures/` | ≥2 objects (good_proc + bad_proc) | ✅ PASS |
| 2 | `test_yields_sql_objects_with_source` | Any fixture file | All objects have non-empty source | ✅ PASS |
| 3 | `test_filter_by_type` | Scope filtered to "Stored Procedure" only | No Table objects returned | ✅ PASS |
| 4 | `test_nonexistent_directory_raises` | Non-existent path | Raises exception | ✅ PASS |
| 5 | `test_source_lines_populated` | Any fixture | obj.source_lines is non-empty list | ✅ PASS |
| 6 | `test_source_upper_populated` | Any fixture | obj.source_upper is uppercase string | ✅ PASS |

---

## 7. Integration Test Cases — Analyser Pipeline

### TC-PIPE-001 — End-to-end analysis from files

| Field | Value |
|-------|-------|
| **Test ID** | TC-PIPE-001 |
| **Type** | Manual |
| **Prerequisite** | SQL files present in configured `source.file_path` |

**Steps:**
1. `dbanalyser run --config analysis_config.yaml --no-persist --format json`
2. Check terminal output shows object count > 0
3. Open `output/dbanalyser_<label>.json`
4. Verify JSON has `run` and `findings` keys
5. Verify `run.total_issues` matches `len(findings)`

**Expected:** All steps complete without error. JSON is valid and consistent.

---

### TC-PIPE-002 — Compliance pack activation

| Field | Value |
|-------|-------|
| **Test ID** | TC-PIPE-002 |
| **Type** | Manual |

**Steps:**
1. Edit `analysis_config.yaml`: set `compliance.enabled_packs: [sox]`
2. `dbanalyser run --no-persist --format json`
3. In the JSON output, check that findings include any with `category: "Compliance-SOX"`

**Expected:** SOX findings appear in output when the pack is enabled.

---

### TC-PIPE-003 — `--no-persist` skips PostgreSQL

| Field | Value |
|-------|-------|
| **Test ID** | TC-PIPE-003 |
| **Type** | Manual |

**Steps:**
1. Stop PostgreSQL service
2. `dbanalyser run --no-persist`
3. Check output

**Expected:** Analysis completes successfully with no PostgreSQL errors.

---

## 8. Integration Test Cases — Config Loader

### TC-CFG-001 — YAML loads all sections

| **Steps** | **Expected** |
|-----------|-------------|
| `python -c "from dbanalyser.config import load_config; c=load_config(); print(c.api.port)"` | Prints `8000` |

### TC-CFG-002 — Environment variable override

| **Steps** | **Expected** |
|-----------|-------------|
| `set DBANALYSER_POSTGRES_PASSWORD=testpass && python -c "from dbanalyser.config import load_config; c=load_config(); print(c.postgres.password)"` | Prints `testpass` |

### TC-CFG-003 — Legacy YAML keys accepted

| **Steps** | **Expected** |
|-----------|-------------|
| Create YAML with `source_mode: file` (old key) | `cfg.source.mode == "file"` — no validation error |

### TC-CFG-004 — `db_schema` alias

| **Steps** | **Expected** |
|-----------|-------------|
| YAML with `postgres.schema: myschema` (old key name) | `cfg.postgres.db_schema == "myschema"` |

---

## 9. API Test Cases

Start the API before running these tests:
```bash
dbanalyser api --port 8000
```

### TC-API-001 — Health check (no auth)

```bash
curl -s http://localhost:8000/health
```
**Expected:**
```json
{"status": "ok", "service": "DBAnalyser API", "version": "2.0.0"}
```
**HTTP status:** 200

---

### TC-API-002 — Root endpoint (no auth)

```bash
curl -s http://localhost:8000/
```
**Expected:** JSON with `service`, `docs`, `health` keys. **HTTP status:** 200

---

### TC-API-003 — Auth rejected without key (when key configured)

```bash
# First set api_key: "testkey" in config, restart API
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/databases
```
**Expected HTTP status:** 401

---

### TC-API-004 — Auth accepted with correct key

```bash
curl -s -H "X-API-Key: testkey" http://localhost:8000/databases
```
**Expected:** JSON with `databases` array. **HTTP status:** 200

---

### TC-API-005 — List runs

```bash
curl -s -H "X-API-Key: testkey" "http://localhost:8000/runs?limit=5"
```
**Expected:** JSON with `runs` array and `total` field. **HTTP status:** 200

---

### TC-API-006 — Trigger analysis job

```bash
curl -s -X POST \
  -H "X-API-Key: testkey" \
  -H "Content-Type: application/json" \
  -d '{"all_dbs": false, "label": "api-test", "no_persist": true}' \
  http://localhost:8000/runs/trigger
```
**Expected:** JSON with `job_id` (UUID), `status: "queued"`. **HTTP status:** 200

---

### TC-API-007 — Poll job status

```bash
JOB_ID=<value from TC-API-006>
curl -s -H "X-API-Key: testkey" "http://localhost:8000/runs/jobs/$JOB_ID"
```
**Expected:** JSON with `status` one of: queued / running / done / failed. **HTTP status:** 200

---

### TC-API-008 — Get findings for a run

```bash
curl -s -H "X-API-Key: testkey" \
  "http://localhost:8000/findings/run/1?severity=Critical&limit=10"
```
**Expected:** JSON with `findings` array filtered to Critical only. **HTTP status:** 200 or 404 if run 1 doesn't exist.

---

### TC-API-009 — Findings summary

```bash
curl -s -H "X-API-Key: testkey" http://localhost:8000/findings/summary/1
```
**Expected:** JSON with `critical`, `high`, `medium`, `low`, `total` fields.

---

### TC-API-010 — Update finding status

```bash
curl -s -X PATCH \
  -H "X-API-Key: testkey" \
  -H "Content-Type: application/json" \
  -d '{"status": "acknowledged", "reason": "Will fix in Q3", "jira": "DB-001"}' \
  http://localhost:8000/findings/1/status
```
**Expected:** JSON with `message: "Finding 1 status → acknowledged"`. **HTTP status:** 200

---

### TC-API-011 — Download Excel report

```bash
curl -s -H "X-API-Key: testkey" \
  "http://localhost:8000/reports/download/1?fmt=excel" \
  -o test_report.xlsx
```
**Expected:** `test_report.xlsx` is a valid Excel file, opens without errors.

---

### TC-API-012 — Health gate — pass scenario

```bash
curl -s -H "X-API-Key: testkey" \
  "http://localhost:8000/reports/health-gate/1?min_health=0&max_critical=999&max_high=999"
```
**Expected:** `{"gate": "PASSED", ...}`. **HTTP status:** 200

---

### TC-API-013 — Health gate — fail scenario

```bash
curl -s -H "X-API-Key: testkey" \
  "http://localhost:8000/reports/health-gate/1?min_health=100&max_critical=0"
```
**Expected:** `{"gate": "FAILED", "reasons": [...]}`. **HTTP status:** 422

---

### TC-API-014 — Trend for database

```bash
curl -s -H "X-API-Key: testkey" \
  "http://localhost:8000/trend/LTFS_DEV?limit=30"
```
**Expected:** JSON with `db_name` and `points` array (may be empty if no runs yet). **HTTP status:** 200 or 404

---

### TC-API-015 — Estate trend summary

```bash
curl -s -H "X-API-Key: testkey" http://localhost:8000/trend/all
```
**Expected:** JSON array, one entry per registered database. **HTTP status:** 200

---

### TC-API-016 — Unsupported report format

```bash
curl -s -H "X-API-Key: testkey" \
  "http://localhost:8000/reports/download/1?fmt=pdf"
```
**Expected:** `{"detail": "Unsupported format 'pdf'..."}`. **HTTP status:** 400

---

## 10. CLI Test Cases

### TC-CLI-001 — Version flag

```bash
dbanalyser --version
```
**Expected:** `DBAnalyser, version 2.0.0`

---

### TC-CLI-002 — Help output

```bash
dbanalyser --help
```
**Expected:** Lists all commands: run, report, dashboard, api, validate, init-db, history, diff, db

---

### TC-CLI-003 — Run with --no-persist

```bash
dbanalyser run --no-persist --format json
```
**Expected:** Completes without PostgreSQL error, JSON report created in `./output/`

---

### TC-CLI-004 — Validate connections

```bash
dbanalyser validate
```
**Expected:** Output shows ✓ or ✗ per connection with descriptive message. Does not crash.

---

### TC-CLI-005 — History (empty)

```bash
dbanalyser history --limit 5
```
**Expected:** Shows table with runs, or "No runs found." — no crash.

---

### TC-CLI-006 — DB list (no PostgreSQL)

```bash
# With PostgreSQL stopped
dbanalyser db list
```
**Expected:** Falls back to config file databases with yellow warning — no crash.

---

### TC-CLI-007 — API command — verify it starts

```bash
dbanalyser api --port 8999 &
sleep 2
curl -s http://localhost:8999/health
kill %1
```
**Expected:** Health endpoint returns `{"status": "ok", ...}`

---

### TC-CLI-008 — Diff two run IDs

```bash
dbanalyser diff 1 2
```
**Expected:** Shows `+ N new`, `- N resolved`, `N unchanged` summary. No crash even if IDs don't exist.

---

## 11. React UI Test Cases

**Prerequisite:** Backend API running (`python3 -m dbanalyser api`) and React dev server running (`npm run dev` inside `dbanalyser-ui/`). Open `http://localhost:5173`.

---

### TC-UI-001 — Application loads and auto-login (auth disabled)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open `http://localhost:5173` | Login page appears |
| 2 | Auth disabled mode | Browser auto-redirects to Dashboard without entering credentials |
| 3 | Verify top bar | Shows `anonymous` user indicator, no Logout button |

---

### TC-UI-002 — Top bar: Database and Run selector

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open any page | Top bar Database dropdown populated from `GET /databases` |
| 2 | Select a database | Run dropdown updates to show runs for that database only |
| 3 | Select a run | All pages (Analysis, Compliance, Reports) load findings for that run |
| 4 | No databases in API | Dropdown shows "No databases registered" placeholder |

---

### TC-UI-003 — Dashboard: Estate Overview tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click Dashboard in sidebar | Estate Overview tab active |
| 2 | Verify KPI row | Shows: Databases count, Overall Health %, Total Findings, Critical Issues, Last Run date |
| 3 | Health Score bar chart | Renders one bar per registered database, coloured by score (green/amber/red) |
| 4 | Findings by Severity donut | Renders with Critical/High/Medium/Low legend |
| 5 | Database cards | One card per registered database with health bar |

---

### TC-UI-004 — Dashboard: Run History tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click "Run History" tab on Dashboard | Table renders |
| 2 | Verify columns | Run label, Database, Date, Health, Findings present |
| 3 | Empty state | Shows "No runs found" message, no crash |

---

### TC-UI-005 — Analysis: Overview tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click Analysis in sidebar | Page loads |
| 2 | No run selected | Subtitle says "Select a run from the top bar to load findings" |
| 3 | Select a run | KPI row: Total Findings + Critical + High + Medium + Low cards rendered |
| 4 | Category bar chart | Renders correctly with coloured bars per category |
| 5 | Severity donut | Renders with legend |

---

### TC-UI-006 — Analysis: Issues Explorer tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click "Issues Explorer" tab | Filter bar + table rendered |
| 2 | Type in search box | Table filters to matching rows in real time |
| 3 | Select "Critical" from Severity dropdown | Only Critical rows shown |
| 4 | Select a category | Table filtered to that category only |
| 5 | Clear filters | All findings shown (up to 100 rows) |
| 6 | > 100 findings | Footer shows "Showing 100 of N findings" |

---

### TC-UI-007 — Analysis: Risk Scoreboard tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click "Risk Scoreboard" tab | Table renders |
| 2 | Verify sort | Objects ordered by total findings descending |
| 3 | Critical column | Non-zero critical counts shown in red |

---

### TC-UI-008 — Schema Quality page

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click Schema Quality in sidebar | Page loads |
| 2 | Overview tab | KPI cards and object distribution chart rendered |
| 3 | "Tables Without PK" tab | Table lists objects with no PK (or empty-state message) |
| 4 | "Index Issues" tab | Index finding cards rendered |
| 5 | "Column Types" tab | Column type findings listed |
| 6 | "Orphan & Unused" tab | Orphan objects listed or empty-state shown |

---

### TC-UI-009 — Compliance page

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click Compliance in sidebar | Overview tab loads |
| 2 | No run selected | Amber info banner shown: "Select a run from the top bar" |
| 3 | Select run with compliance findings | KPI cards update, chart renders |
| 4 | Click "SOX" tab | FindingsTable shows Compliance-SOX findings only |
| 5 | Click a finding row | Row expands to show Issue, Recommendation, Code Snippet |
| 6 | Click expanded row again | Row collapses |
| 7 | GDPR / RBI / Security / Dangerous SQL tabs | Each shows its respective filtered findings |
| 8 | Run with zero compliance findings | Each tab shows "No compliance findings" message |

---

### TC-UI-010 — Reports: Download Report tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click Reports in sidebar | Download Report tab active |
| 2 | No run selected | Download button disabled |
| 3 | Select JSON format | Button label changes to "Download JSON Report" |
| 4 | Click Download | Browser downloads `dbanalyser_report_run<id>.json` |
| 5 | Select CSV format and download | Browser downloads `.csv` file |
| 6 | Quick-download from Available Runs | Row download button fetches JSON with auth header |

---

### TC-UI-011 — Reports: Health Gate tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click "Health Gate" tab | Gate result card renders |
| 2 | Run health >= threshold | PASS status shown in green |
| 3 | Run health < threshold | FAIL status shown in red |
| 4 | No run selected | Empty state shown |

---

### TC-UI-012 — Live DB page

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click Live DB in sidebar | Overview tab loads |
| 2 | KPI cards | Reflect findings from latest live-scan run |
| 3 | "Run Live Scan" tab | Database dropdown and Trigger button visible |
| 4 | Select database and click Trigger | `POST /runs/trigger` called; success message shown |
| 5 | Trigger with no database selected | Button disabled or shows validation error |

---

### TC-UI-013 — Administration: Databases tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click Administration in sidebar | Databases tab active |
| 2 | Database table | Shows all registered databases with host, port, environment, status |
| 3 | Click "+ Add Database" | Registration form expands |
| 4 | Fill form and submit | `POST /databases` called; new database appears in table |
| 5 | Click "Edit" on a database | Alert shown: "Remove and re-register to edit" |
| 6 | Click "Remove" on a database | Confirmation dialog; `DELETE /databases/{name}` called |

---

### TC-UI-014 — Administration: Schedules tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click "Schedules" tab | Schedule table and "Add Schedule" form shown |
| 2 | Select CRON preset | Cron expression field populates |
| 3 | Fill name and database, click Add | Schedule appears in table, saved to localStorage |
| 4 | Toggle enable/disable | Schedule status updates immediately |
| 5 | Click "Trigger Now" | `POST /runs/trigger` called; success toast shown |
| 6 | Click "Remove" | Schedule deleted from table and localStorage |

---

### TC-UI-015 — Administration: Users & Org tab

| Step | Action | Expected |
|------|--------|----------|
| 1 | Auth disabled mode | Invite and Change Password forms shown but return 401 (expected) |
| 2 | Auth enabled mode | Invite user via `POST /auth/invite`; success message shown |
| 3 | Change password | `POST /auth/change-password` called |

---

### TC-UI-016 — No data / empty state handling

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open Analysis with no runs in PostgreSQL | "Select a run from the top bar to load findings" shown |
| 2 | Open Compliance with no findings | Each tab shows appropriate empty-state message |
| 3 | Open Reports with no runs | Download button disabled, Available Runs panel empty |
| 4 | Open Live DB with no live runs | KPI cards show 0, performance tabs show empty state |

---

### TC-UI-017 — Responsive and visual checks

| Step | Action | Expected |
|------|--------|----------|
| 1 | All pages on 1440×900 | No horizontal scrollbar; no layout overflow |
| 2 | Severity badges | Critical = red, High = amber, Medium = blue, Low = green |
| 3 | Charts on Overview and Analysis | Render within card boundaries, no overflow |

---

## 12. Regression Test Checklist

Run after every code change before committing:

**Backend (Python):**
- [ ] `python -m pytest tests/ -v --tb=short` — 168 passed, 0 failed
- [ ] `good_proc.sql` produces 0 Critical/High findings
- [ ] `bad_proc.sql` produces ≥ 5 findings
- [ ] `dbanalyser --version` shows `2.0.0`
- [ ] `dbanalyser run --no-persist` completes without error
- [ ] `from dbanalyser.config import load_config; load_config()` — no validation errors
- [ ] `from dbanalyser.engine.rules import build_rule_set; len(build_rule_set(None)) == 44`
- [ ] `from dbanalyser.engine.rules import build_rule_set; from dbanalyser.config import Settings, ComplianceConfig; len(build_rule_set(Settings(compliance=ComplianceConfig(enabled_packs=['sox','gdpr','rbi'])))) == 62`

**React UI (TypeScript):**
- [ ] `cd dbanalyser-ui && npx tsc --noEmit` — zero TypeScript errors
- [ ] `npm run build` — production build completes with no errors
- [ ] Login page loads; auth-disabled mode redirects to Dashboard automatically
- [ ] Dashboard Estate Overview: KPI cards and charts render with seeded data
- [ ] Analysis Issues Explorer: search and severity/category filters work
- [ ] Compliance page: all 6 tabs render; row expand/collapse works
- [ ] Reports: JSON download succeeds; Excel shows informative error
- [ ] Live DB: Trigger button calls `POST /runs/trigger` successfully
- [ ] Administration: Add and Remove database round-trips work

---

## 13. Test Execution Summary

### Automated test results (current baseline)

```
tests/test_compliance.py       39 passed
tests/test_custom_rules.py     27 passed
tests/test_dangerous_sql.py    19 passed
tests/test_rules.py            40 passed
tests/test_scanner.py          14 passed
tests/test_scheduler.py        10 passed
tests/test_webhooks.py         19 passed
─────────────────────────────────────────
TOTAL                         168 passed  |  0 failed  |  0 warnings
Time: ~4 seconds
```

### Rule coverage

| Rule module | Rules defined | Test classes | Detection tests | False-positive tests |
|-------------|--------------|--------------|-----------------|----------------------|
| security.py | 5 | 3 | 5 | 3 |
| reliability.py | 4 | 2 | 3 | 2 |
| performance.py | 8 | 5 | 5 | 4 |
| data_safety.py | 6 | 3 | 3 | 3 |
| best_practices.py | 5 | 3 | 3 | 2 |
| parameter_sniffing.py | 4 | 1 | 1 | 1 |
| maintainability.py | 6 | 1 | 1 | 1 |
| dangerous_sql.py | 6 | 6 | 9 | 9 |
| compliance/sox.py | 6 | 5 | 5 | 4 |
| compliance/gdpr.py | 6 | 5 | 5 | 6 |
| compliance/rbi.py | 6 | 4 | 4 | 4 |
| **Total** | **62** | **38** | **44** | **39** |

---

## 14. Unit Test Cases — Custom Rules (test_custom_rules.py)

### TC-CUSTOM coverage table

| TC ID | Test Method | What it tests | Expected | Status |
|-------|-------------|---------------|----------|--------|
| TC-CUSTOM-001 | `test_load_single_rule_file` | YAML file with one rule loads without error | 1 rule returned | ✅ PASS |
| TC-CUSTOM-002 | `test_load_multiple_rules_from_file` | YAML file with 3 rules | 3 rules returned | ✅ PASS |
| TC-CUSTOM-003 | `test_load_from_directory` | `rules_dir` with 2 YAML files | All rules from both files loaded | ✅ PASS |
| TC-CUSTOM-004 | `test_rule_id_required` | YAML rule missing `id` field | ValidationError raised | ✅ PASS |
| TC-CUSTOM-005 | `test_severity_validated` | Severity = "Blocker" (invalid) | ValidationError raised | ✅ PASS |
| TC-CUSTOM-006 | `test_patterns_required` | Rule with empty `patterns` list | ValidationError raised | ✅ PASS |
| TC-CUSTOM-007 | `test_detection_single_pattern` | Pattern `CURSOR` against SP with DECLARE CURSOR | ≥1 finding | ✅ PASS |
| TC-CUSTOM-008 | `test_no_false_positive_single_pattern` | Pattern `CURSOR` against SP with no cursor | 0 findings | ✅ PASS |
| TC-CUSTOM-009 | `test_detection_multiple_patterns` | Rule with 2 patterns — one matches | ≥1 finding | ✅ PASS |
| TC-CUSTOM-010 | `test_applies_to_object_type_filter` | Rule with `applies_to: [Trigger]` against SP | 0 findings | ✅ PASS |
| TC-CUSTOM-011 | `test_applies_to_allows_trigger` | Same rule against Trigger | ≥1 finding | ✅ PASS |
| TC-CUSTOM-012 | `test_applies_to_all_when_omitted` | Rule without `applies_to` key | Applies to SP, View, Table, Trigger | ✅ PASS |
| TC-CUSTOM-013 | `test_finding_carries_custom_rule_id` | Detection finding | `finding.rule_id == "CUSTOM001"` | ✅ PASS |
| TC-CUSTOM-014 | `test_finding_carries_severity` | Detection finding | `finding.severity` matches YAML definition | ✅ PASS |
| TC-CUSTOM-015 | `test_finding_carries_recommendation` | Detection finding | `finding.recommendation` matches YAML | ✅ PASS |
| TC-CUSTOM-016 | `test_disabled_rule_skipped` | Rule with `enabled: false` | 0 findings (rule not applied) | ✅ PASS |
| TC-CUSTOM-017 | `test_custom_rules_merged_with_builtin` | `build_rule_set()` with custom rules enabled | Custom rules present in rule list | ✅ PASS |
| TC-CUSTOM-018 | `test_duplicate_rule_id_raises` | Two rules with same `id` in one file | ValidationError or RuntimeError | ✅ PASS |
| TC-CUSTOM-019 | `test_empty_yaml_file_ignored` | Empty `.yaml` file in rules_dir | 0 rules loaded, no crash | ✅ PASS |
| TC-CUSTOM-020 | `test_invalid_yaml_syntax_raises` | Malformed YAML | Informative error raised | ✅ PASS |
| TC-CUSTOM-021 | `test_regex_case_insensitive_match` | Pattern `cursor` (lowercase) against `DECLARE CURSOR` | ≥1 finding (case-insensitive) | ✅ PASS |
| TC-CUSTOM-022 | `test_line_number_reported` | Detection on line 5 | `finding.line_number == 5` | ✅ PASS |
| TC-CUSTOM-023 | `test_rules_files_overrides_dir` | Both `rules_dir` and `rules_files` set | Only `rules_files` loaded | ✅ PASS |
| TC-CUSTOM-024 | `test_nonexistent_rules_file_raises` | Path in `rules_files` does not exist | FileNotFoundError raised | ✅ PASS |
| TC-CUSTOM-025 | `test_category_propagated_to_finding` | Custom category "Naming Standards" | `finding.category == "Naming Standards"` | ✅ PASS |
| TC-CUSTOM-026 | `test_multiple_pattern_matches_one_finding_per_match` | Rule with 2 patterns, both match | 2 findings | ✅ PASS |
| TC-CUSTOM-027 | `test_custom_rules_disabled_by_config` | `custom_rules.enabled: false` | 0 custom rules loaded | ✅ PASS |

---

## 15. Unit Test Cases — Webhooks (test_webhooks.py)

### TC-WH coverage table

| TC ID | Test Method | What it tests | Expected | Status |
|-------|-------------|---------------|----------|--------|
| TC-WH-001 | `test_slack_webhook_called_on_findings` | Run produces Critical finding with Slack URL configured | `requests.post` called once with Slack URL | ✅ PASS |
| TC-WH-002 | `test_teams_webhook_called_on_findings` | Run produces Critical finding with Teams URL configured | `requests.post` called once with Teams URL | ✅ PASS |
| TC-WH-003 | `test_both_webhooks_called` | Both Slack and Teams URLs configured | `requests.post` called twice | ✅ PASS |
| TC-WH-004 | `test_no_call_when_notifications_disabled` | `notifications.enabled: false` | `requests.post` never called | ✅ PASS |
| TC-WH-005 | `test_no_call_below_min_findings` | 0 findings, `min_findings_to_alert: 1` | No webhook call | ✅ PASS |
| TC-WH-006 | `test_alert_on_critical_only` | High finding, `alert_on_severity: [Critical]` | No webhook call | ✅ PASS |
| TC-WH-007 | `test_alert_on_high_triggers` | High finding, `alert_on_severity: [Critical, High]` | Webhook called | ✅ PASS |
| TC-WH-008 | `test_slack_payload_contains_health_score` | Slack payload | Payload JSON contains `health_score` key | ✅ PASS |
| TC-WH-009 | `test_slack_payload_contains_run_label` | Slack payload | Payload contains run label string | ✅ PASS |
| TC-WH-010 | `test_slack_payload_contains_severity_counts` | Slack payload | Payload contains critical/high/medium/low counts | ✅ PASS |
| TC-WH-011 | `test_teams_payload_is_adaptive_card` | Teams payload | `payload["type"] == "AdaptiveCard"` | ✅ PASS |
| TC-WH-012 | `test_http_error_logged_not_raised` | Slack endpoint returns 500 | Warning logged, no exception propagated | ✅ PASS |
| TC-WH-013 | `test_connection_error_logged_not_raised` | `requests.post` raises `ConnectionError` | Warning logged, analysis result unaffected | ✅ PASS |
| TC-WH-014 | `test_no_call_when_slack_url_blank` | `slack_webhook_url: ""` | No Slack call | ✅ PASS |
| TC-WH-015 | `test_no_call_when_teams_url_blank` | `teams_webhook_url: ""` | No Teams call | ✅ PASS |
| TC-WH-016 | `test_min_findings_zero_always_alerts` | 0 findings, `min_findings_to_alert: 0` | Webhook called | ✅ PASS |
| TC-WH-017 | `test_timeout_used_in_post` | Mocked `requests.post` | Called with `timeout` argument | ✅ PASS |
| TC-WH-018 | `test_db_name_included_in_payload` | Payload for named database run | Payload contains `db_name` field | ✅ PASS |
| TC-WH-019 | `test_notify_called_after_analysis_completes` | Full analysis run with notification config | Notification sent after findings are complete | ✅ PASS |

---

## 16. Unit Test Cases — Scheduler (test_scheduler.py)

### TC-SCHED coverage table

| TC ID | Test Method | What it tests | Expected | Status |
|-------|-------------|---------------|----------|--------|
| TC-SCHED-001 | `test_add_task_persists_to_db` | `schedule add` call | Row inserted into `scheduled_tasks` table | ✅ PASS |
| TC-SCHED-002 | `test_list_tasks_returns_all` | `schedule list` with 3 tasks | 3 rows returned | ✅ PASS |
| TC-SCHED-003 | `test_remove_task_deletes_row` | `schedule remove` by name | Row deleted from `scheduled_tasks` | ✅ PASS |
| TC-SCHED-004 | `test_remove_nonexistent_raises` | Remove task that does not exist | Informative error message | ✅ PASS |
| TC-SCHED-005 | `test_next_run_computed_on_add` | Add task with cron `0 2 * * *` | `next_run_at` is set to the next 02:00 UTC | ✅ PASS |
| TC-SCHED-006 | `test_run_due_fires_overdue_task` | Task with `next_run_at` in the past | Analysis triggered, `last_run_at` updated | ✅ PASS |
| TC-SCHED-007 | `test_run_due_skips_future_task` | Task with `next_run_at` 1 hour from now | No analysis triggered | ✅ PASS |
| TC-SCHED-008 | `test_run_due_skips_inactive_task` | Task with `is_active: false` | No analysis triggered | ✅ PASS |
| TC-SCHED-009 | `test_next_run_updated_after_fire` | Task fires via `run-due` | `next_run_at` advanced to next cron occurrence | ✅ PASS |
| TC-SCHED-010 | `test_scheduler_disabled_by_config` | `scheduler.enabled: false` | Background thread not started; no tasks polled | ✅ PASS |
