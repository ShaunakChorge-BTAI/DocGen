"""Seed PostgreSQL with LTFS_DEV database entry and sample analysis run."""
import psycopg2
import json
import uuid
import hashlib
from datetime import datetime, timedelta

conn = psycopg2.connect(host='localhost', port=5432, database='dbanalyser',
                        user='postgres', password='sa')
conn.autocommit = True
cur = conn.cursor()

# 1. Register LTFS_DEV
cur.execute("""
    INSERT INTO db_registry (name, environment, host, port, database_name, use_windows_auth,
                             description, owner_label, tags, is_active)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (name) DO UPDATE SET environment=EXCLUDED.environment, updated_at=NOW()
    RETURNING id
""", ('LTFS_DEV','development','localhost',1433,'LTFS_Dev',True,
      'Local development database','DBA Team',['dev'],True))
db_id = cur.fetchone()[0]
print(f"db_registry id={db_id}")

# 2. Insert a run
run_uuid = str(uuid.uuid4())
cur.execute("""
    INSERT INTO runs (run_id, db_registry_id, label, timestamp, environment, source_mode,
                      database_name, host, duration_sec, total_objects, total_issues,
                      critical_count, high_count, medium_count, low_count, health_score, status)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    RETURNING id
""", (run_uuid, db_id, 'Initial Scan - LTFS_DEV', datetime.now(), 'development', 'file',
      'LTFS_Dev', 'localhost', 142.5, 47, 25, 5, 8, 8, 4, 62.3, 'completed'))
run_id = cur.fetchone()[0]
print(f"run id={run_id}")

# 3. Sample findings
findings = [
    ('usp_ProcessLoan',     'Stored Procedure', 'Security',        'SEC001', 'Critical',
     'SQL injection risk: dynamic SQL built from @LoanId without parameterization',
     'Use sp_executesql with typed parameters', 45),
    ('usp_ProcessLoan',     'Stored Procedure', 'Security',        'SEC002', 'Critical',
     'Hardcoded connection string found in procedure body',
     'Move to config table or environment variable', 112),
    ('usp_GetCustomer',     'Stored Procedure', 'Performance',     'PER001', 'High',
     'SELECT * used — fetches all columns including large BLOBs',
     'Specify only required columns in SELECT list', 8),
    ('usp_GetCustomer',     'Stored Procedure', 'Performance',     'PER003', 'High',
     'Scalar UDF called inside WHERE clause — prevents index seek',
     'Inline the UDF logic or use computed column', 23),
    ('usp_UpdateBalance',   'Stored Procedure', 'Reliability',     'REL001', 'High',
     'Missing SET XACT_ABORT ON — partial updates possible on error',
     'Add SET XACT_ABORT ON at procedure start', 2),
    ('usp_UpdateBalance',   'Stored Procedure', 'Dangerous SQL',   'DNG001', 'Critical',
     'UPDATE statement without WHERE clause — will update ALL rows',
     'Add WHERE clause to restrict update scope', 67),
    ('vw_CustomerSummary',  'View',             'Performance',     'PER002', 'High',
     'Cursor used in view — row-by-row processing severely degrades performance',
     'Rewrite using set-based operations', 15),
    ('vw_LoanStatus',       'View',             'Best Practices',  'BP001',  'Medium',
     'View lacks schema prefix on referenced table dbo.Loans',
     'Always qualify with schema: dbo.Loans', 3),
    ('usp_AuditLog',        'Stored Procedure', 'Compliance-SOX',  'SOX001', 'High',
     'Financial table tbl_Transactions missing CreatedBy audit column',
     'Add CreatedBy, ModifiedBy, ModifiedAt columns', 1),
    ('usp_GetPersonalData', 'Stored Procedure', 'Compliance-GDPR', 'GDPR001','High',
     'SELECT * on tbl_Customers exposes PII columns (email, phone, dob)',
     'Explicitly list non-PII columns only', 5),
    ('usp_GetPersonalData', 'Stored Procedure', 'Compliance-GDPR', 'GDPR003','Medium',
     'Unmasked email column returned in result set without consent check',
     'Apply GDPR masking or add consent validation', 12),
    ('usp_TransferFunds',   'Stored Procedure', 'Compliance-RBI',  'RBI001', 'Critical',
     'Transaction amount stored without ENCRYPTBYKEY — RBI data-at-rest rule',
     'Encrypt sensitive financial columns', 89),
    ('usp_TransferFunds',   'Stored Procedure', 'Compliance-RBI',  'RBI005', 'High',
     'Transaction block missing TRY/CATCH + ROLLBACK — funds transfer risk',
     'Wrap in TRY/CATCH with explicit ROLLBACK', 34),
    ('usp_ReportGenerate',  'Stored Procedure', 'Maintainability', 'MNT001', 'Medium',
     'Procedure has 687 lines — exceeds 500-line threshold',
     'Split into smaller focused procedures', 1),
    ('usp_ReportGenerate',  'Stored Procedure', 'Maintainability', 'MNT002', 'Medium',
     'Nesting depth of 6 exceeds maximum of 4',
     'Refactor nested conditions into helper procedures', 234),
    ('usp_SearchLoans',     'Stored Procedure', 'Parameter Sniffing','PS001','High',
     'Optional parameter @Status used directly in WHERE — parameter sniffing risk',
     'Use OPTION(RECOMPILE) or local variable copy', 18),
    ('tbl_Repayments',      'Table',            'Best Practices',  'BP002',  'Medium',
     'Table tbl_Repayments has no primary key defined',
     'Add a primary key column (e.g. RepaymentId INT IDENTITY)', 1),
    ('usp_CalcInterest',    'Stored Procedure', 'Performance',     'PER004', 'Medium',
     'NOLOCK hint used on tbl_Accounts — dirty reads of financial data',
     'Remove NOLOCK; use READ COMMITTED SNAPSHOT instead', 44),
    ('usp_CalcInterest',    'Stored Procedure', 'Data Safety',     'DS001',  'High',
     'NULL comparison using = NULL instead of IS NULL — always evaluates to unknown',
     'Replace = NULL with IS NULL', 67),
    ('usp_BatchClose',      'Stored Procedure', 'Dangerous SQL',   'DNG002', 'Critical',
     'DELETE without WHERE clause — will delete entire table contents',
     'Add WHERE clause; consider archiving before deletion', 22),
    ('usp_BatchClose',      'Stored Procedure', 'Reliability',     'REL002', 'High',
     'Missing TRY/CATCH block in procedure that performs bulk DML',
     'Wrap DML in TRY/CATCH with ROLLBACK on error', 5),
    ('vw_ActiveLoans',      'View',             'Performance',     'PER005', 'Low',
     'ORDER BY without TOP/FETCH in view — result order not guaranteed',
     'Remove ORDER BY or add TOP clause', 8),
    ('usp_GetLoanDetails',  'Stored Procedure', 'Best Practices',  'BP003',  'Low',
     'Procedure name uses sp_ prefix — conflicts with system procedure resolution',
     'Rename: remove sp_ prefix, use usp_ instead', 1),
    ('usp_GetLoanDetails',  'Stored Procedure', 'Maintainability', 'MNT003', 'Low',
     'Magic number 0.18 found in calculation — should be a named config value',
     'Replace with config table lookup or named constant', 78),
    ('usp_SendNotification','Stored Procedure', 'Security',        'SEC003', 'Critical',
     'xp_cmdshell call detected — direct OS command execution risk',
     'Remove xp_cmdshell; use Service Broker or CLR safely', 15),
]

for row in findings:
    cur.execute("""
        INSERT INTO findings (run_id, object_name, object_type, schema_name, category,
                              rule_id, severity, issue, recommendation, line_number,
                              status, is_new)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (run_id, row[0], row[1], 'dbo', row[2], row[3], row[4],
          row[5], row[6], row[7], 'open', True))
print(f"Inserted {len(findings)} findings")

# 4. Object snapshots
objects = [
    ('usp_ProcessLoan',     'Stored Procedure', 687, 4, 'Critical'),
    ('usp_GetCustomer',     'Stored Procedure', 145, 2, 'High'),
    ('usp_UpdateBalance',   'Stored Procedure', 234, 3, 'Critical'),
    ('vw_CustomerSummary',  'View',              89, 2, 'High'),
    ('vw_LoanStatus',       'View',              45, 1, 'Low'),
    ('usp_AuditLog',        'Stored Procedure', 312, 1, 'High'),
    ('usp_GetPersonalData', 'Stored Procedure', 178, 2, 'High'),
    ('usp_TransferFunds',   'Stored Procedure', 456, 3, 'Critical'),
    ('usp_ReportGenerate',  'Stored Procedure', 687, 2, 'Medium'),
    ('usp_SearchLoans',     'Stored Procedure', 223, 1, 'High'),
    ('tbl_Repayments',      'Table',             12, 1, 'Medium'),
    ('usp_CalcInterest',    'Stored Procedure', 189, 2, 'Medium'),
    ('usp_BatchClose',      'Stored Procedure', 134, 3, 'Critical'),
    ('vw_ActiveLoans',      'View',              67, 1, 'Low'),
    ('usp_GetLoanDetails',  'Stored Procedure', 298, 2, 'Low'),
    ('usp_SendNotification','Stored Procedure',  89, 1, 'Critical'),
]
for obj_name, obj_type, lines, issues, risk in objects:
    content_hash = hashlib.md5(obj_name.encode()).hexdigest()
    cur.execute("""
        INSERT INTO object_snapshots (run_id, object_name, object_type, schema_name,
                                      content_hash, lines, issue_count, risk_level)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (run_id, obj_name, obj_type, 'dbo', content_hash, lines, issues, risk))
print(f"Inserted {len(objects)} object snapshots")

# 5. Health trend — current run
cur.execute("""
    INSERT INTO health_trend (run_id, db_registry_id, db_name, environment, timestamp,
                              health_score, total_objects, total_issues,
                              critical_count, high_count, medium_count, low_count)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", (run_id, db_id, 'LTFS_DEV', 'development', datetime.now(),
      62.3, 47, 25, 5, 8, 8, 4))

# Historical trend points — insert as separate runs
for i in range(1, 6):
    ts = datetime.now() - timedelta(days=i * 3)
    h  = round(min(100, 62.3 + i * 5.2), 1)
    c  = max(0, 5 - i)
    hi = max(0, 8 - i)
    hist_uuid = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO runs (run_id, db_registry_id, label, timestamp, environment, source_mode,
                          database_name, host, duration_sec, total_objects, total_issues,
                          critical_count, high_count, medium_count, low_count, health_score, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (hist_uuid, db_id, f'Historical Scan -{i}', ts, 'development', 'file',
          'LTFS_Dev', 'localhost', 130.0, 47, max(10, 25 - i * 3), c, hi,
          max(4, 8 - i), max(2, 4 - i), h, 'completed'))
    hist_run_id = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO health_trend (run_id, db_registry_id, db_name, environment, timestamp,
                                  health_score, total_objects, total_issues,
                                  critical_count, high_count, medium_count, low_count)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (hist_run_id, db_id, 'LTFS_DEV', 'development', ts,
          h, 47, max(10, 25 - i * 3), c, hi, max(4, 8 - i), max(2, 4 - i)))
print("Inserted health trend (current + 5 historical)")

# 6. Update db_registry last run stats
cur.execute("""
    UPDATE db_registry SET last_run_at=NOW(), last_health=62.3 WHERE id=%s
""", (db_id,))

print("\nAll done! PostgreSQL seeded successfully.")
conn.close()
