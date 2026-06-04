"""
RBI (Reserve Bank of India) Compliance Rule Pack
=================================================
Rules enforce data governance patterns required for RBI IT Framework compliance,
focusing on financial data security, transaction integrity, audit trails,
and access controls on core banking objects.

Rule IDs: RBI001 – RBI006
"""

from __future__ import annotations

import re
from typing import List

from dbanalyser.engine.rules.base import BaseRule, RuleFinding, SQLObject

# Core banking / RBI-sensitive table/object name patterns.
# No \b boundaries — matches keywords inside CamelCase names like
# "usp_ExportRemittance", "BankAccountDetails", "txn_log" etc.
_RBI_SENSITIVE_RE = re.compile(
    r'account|transaction|txn|transfer|remittance|payment|loan|'
    r'deposit|withdrawal|ledger|journal|neft|rtgs|imps|upi|'
    r'kyc|aml|ifsc|swift|beneficiary|nominee|mandate|emi|'
    r'interest|penalty|charge|fee|balance|credit|debit',
    re.IGNORECASE,
)

_ENCRYPTION_HINT_RE = re.compile(
    r'\b(ENCRYPTBYKEY|ENCRYPTBYCERT|ENCRYPTBYPASSPHRASE|'
    r'HASHBYTES|CONVERT.*VARBINARY|ColumnEncryption|'
    r'ALWAYS ENCRYPTED|MASKED WITH)\b',
    re.IGNORECASE,
)

# Handles both plain (TransactionAudit) and schema-qualified (dbo.TransactionAudit)
_AUDIT_TABLE_RE = re.compile(
    r'\bINSERT\s+INTO\s+(?:\[?\w+\]?\.)?\[?\w*(audit|log|trail|history)\w*\]?\b',
    re.IGNORECASE,
)


def _is_rbi_sensitive(obj: SQLObject) -> bool:
    return bool(_RBI_SENSITIVE_RE.search(obj.name) or
                _RBI_SENSITIVE_RE.search(obj.source[:600]))


class RbiUnencryptedFinancialDataRule(BaseRule):
    """RBI001 — Financial table stores sensitive columns without encryption hints."""
    rule_id  = "RBI001"
    category = "Compliance-RBI"

    # Column names that should ideally be encrypted at rest
    _SENSITIVE_COLS = re.compile(
        r'\b(account_?no|account_?number|card_?no|card_?number|'
        r'cvv|pin|password|ifsc_?code|swift_?code|pan_?no|'
        r'aadhaar|aadhar|mobile_?no|phone_?no)\b',
        re.IGNORECASE,
    )

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Table":
            return []
        if not _is_rbi_sensitive(obj):
            return []
        src = obj.source
        has_sensitive_col = bool(self._SENSITIVE_COLS.search(src))
        if not has_sensitive_col:
            return []
        has_encryption = bool(_ENCRYPTION_HINT_RE.search(src))
        if not has_encryption:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Critical",
                issue=(
                    f"Financial table '{obj.name}' contains sensitive columns without encryption"
                ),
                recommendation=(
                    "RBI IT Framework Section 9 requires sensitive financial data to be encrypted "
                    "at rest. Use SQL Server Always Encrypted, column-level encryption (ENCRYPTBYKEY), "
                    "or Transparent Data Encryption (TDE) for the database."
                ),
                line_number=1,
            )]
        return []


class RbiMissingTransactionAuditRule(BaseRule):
    """RBI002 — Financial stored procedure modifies data without writing to an audit log."""
    rule_id  = "RBI002"
    category = "Compliance-RBI"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("Stored Procedure", "Trigger"):
            return []
        if not _is_rbi_sensitive(obj):
            return []
        src = self._safe_source(obj)
        has_dml = bool(re.search(
            r'\b(INSERT\s+INTO|UPDATE|DELETE)\b', src, re.IGNORECASE
        ))
        if not has_dml:
            return []
        has_audit = bool(_AUDIT_TABLE_RE.search(src))
        if not has_audit:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Critical",
                issue=(
                    f"Financial object '{obj.name}' modifies data without writing to an audit log"
                ),
                recommendation=(
                    "RBI mandates a complete audit trail for all financial transactions. "
                    "Every DML on core banking tables must insert a record into a corresponding "
                    "audit/history table capturing: timestamp, user, old value, new value, IP."
                ),
                line_number=1,
            )]
        return []


class RbiDirectTableAccessRule(BaseRule):
    """RBI003 — Direct SELECT/DML on a sensitive financial table (bypass stored procedure layer)."""
    rule_id  = "RBI003"
    category = "Compliance-RBI"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        # Flag ad-hoc scripts or views that directly query core banking tables
        if obj.obj_type not in ("View", "Table"):
            return []
        if not _is_rbi_sensitive(obj):
            return []
        src = self._safe_source(obj)
        # A View that directly queries sensitive tables without row-level filtering
        has_where = bool(re.search(r'\bWHERE\b', src, re.IGNORECASE))
        if obj.obj_type == "View" and not has_where:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue=(
                    f"View '{obj.name}' exposes financial table data without row-level filtering"
                ),
                recommendation=(
                    "Views on financial tables should include a WHERE clause to restrict "
                    "data to authorised records. Consider using row-level security (RLS) policies "
                    "or restrict view access by role."
                ),
                line_number=1,
            )]
        return []


class RbiMissingRowLevelSecurityRule(BaseRule):
    """RBI004 — Financial table definition has no RLS policy reference or comment."""
    rule_id  = "RBI004"
    category = "Compliance-RBI"

    _RLS_HINT_RE = re.compile(
        r'\b(ROW_?LEVEL_?SECURITY|SECURITY POLICY|CREATE POLICY|'
        r'rls|row.?security|fn_securitypredicate)\b',
        re.IGNORECASE,
    )

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Table":
            return []
        if not _is_rbi_sensitive(obj):
            return []
        has_rls = bool(self._RLS_HINT_RE.search(obj.source))
        if not has_rls:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue=(
                    f"Financial table '{obj.name}' has no Row-Level Security (RLS) policy reference"
                ),
                recommendation=(
                    "RBI IT Framework requires access to customer financial data to be restricted "
                    "to authorised users. Implement SQL Server Row-Level Security using a security "
                    "policy (CREATE SECURITY POLICY) with a filter predicate."
                ),
                line_number=1,
            )]
        return []


class RbiNoErrorHandlingInFinancialSpRule(BaseRule):
    """RBI005 — Financial stored procedure has no TRY/CATCH or transaction rollback."""
    rule_id  = "RBI005"
    category = "Compliance-RBI"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Stored Procedure":
            return []
        if not _is_rbi_sensitive(obj):
            return []
        src = self._safe_source(obj)
        has_tran = bool(re.search(r'\bBEGIN\s+TRAN(SACTION)?\b', src, re.IGNORECASE))
        if not has_tran:
            return []
        has_try   = bool(re.search(r'\bBEGIN\s+TRY\b', src, re.IGNORECASE))
        has_catch = bool(re.search(r'\bBEGIN\s+CATCH\b', src, re.IGNORECASE))
        has_rollback = bool(re.search(r'\bROLLBACK\b', src, re.IGNORECASE))
        if not (has_try and has_catch and has_rollback):
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue=(
                    f"Financial procedure '{obj.name}' lacks complete TRY/CATCH + ROLLBACK error handling"
                ),
                recommendation=(
                    "All financial transaction procedures must use BEGIN TRY / BEGIN CATCH "
                    "with ROLLBACK TRANSACTION in the CATCH block to ensure atomicity. "
                    "Partial financial writes corrupt ledger integrity."
                ),
                line_number=1,
            )]
        return []


class RbiHardcodedConnectionStringRule(BaseRule):
    """RBI006 — Hardcoded connection string or server reference in financial object."""
    rule_id  = "RBI006"
    category = "Compliance-RBI"

    _CONNSTR_RE = re.compile(
        r"'[^']*(?:Data Source|Server|Initial Catalog|Password|User ID)[^']*'",
        re.IGNORECASE,
    )

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if not _is_rbi_sensitive(obj):
            return []
        findings = []
        for m in self._CONNSTR_RE.finditer(obj.source):
            ln = self.line_of(m, obj.source)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="Hardcoded connection string in financial object — credential exposure risk",
                recommendation=(
                    "RBI security guidelines prohibit hardcoded credentials. "
                    "Store connection strings in encrypted config stores (Azure Key Vault, "
                    "SQL Server Credential objects, or secure application config)."
                ),
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


RBI_RULES: List[BaseRule] = [
    RbiUnencryptedFinancialDataRule(),
    RbiMissingTransactionAuditRule(),
    RbiDirectTableAccessRule(),
    RbiMissingRowLevelSecurityRule(),
    RbiNoErrorHandlingInFinancialSpRule(),
    RbiHardcodedConnectionStringRule(),
]
