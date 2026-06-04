"""
SOX (Sarbanes-Oxley) Compliance Rule Pack
==========================================
Rules focus on financial-data integrity, audit trails, and access controls
that are commonly required for SOX compliance in SQL Server databases.

Rule IDs: SOX001 – SOX006
"""

from __future__ import annotations

import re
from typing import List

from dbanalyser.engine.rules.base import BaseRule, RuleFinding, SQLObject

# Financial-sensitive keywords used to identify relevant objects.
# No \b boundaries — we want to match CamelCase names like "AccountLedger",
# "usp_PostPayment", "LedgerEntry" etc.
_FINANCIAL_KEYWORDS = re.compile(
    r'account|ledger|journal|transaction|payment|invoice|revenue|expense|'
    r'balance|financial|audit|gl_|ap_|ar_|payroll|budget|forecast|remittance',
    re.IGNORECASE,
)

_AUDIT_COLUMNS = frozenset([
    "createdby", "created_by", "createddate", "created_date", "createdon",
    "modifiedby", "modified_by", "modifieddate", "modified_date", "modifiedon",
    "updatedby", "updated_by", "updateddate", "updated_date", "updatedon",
    "changedby", "changed_by", "changeddate", "changed_date",
    "inserted_by", "insertedby", "last_modified_by", "lastmodifiedby",
])


def _is_financial_object(obj: SQLObject) -> bool:
    """Return True if the object name or source suggests financial data."""
    return bool(_FINANCIAL_KEYWORDS.search(obj.name) or
                _FINANCIAL_KEYWORDS.search(obj.source[:500]))


class SoxMissingAuditColumnsRule(BaseRule):
    """SOX001 — Table or procedure lacks audit-trail columns (CreatedBy / ModifiedBy / dates)."""
    rule_id  = "SOX001"
    category = "Compliance-SOX"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if not _is_financial_object(obj):
            return []
        src_lower = obj.source.lower()
        found_audit = any(col in src_lower for col in _AUDIT_COLUMNS)
        if not found_audit:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue=(
                    f"Financial object '{obj.name}' has no audit-trail columns "
                    "(CreatedBy / ModifiedBy / date stamps)"
                ),
                recommendation=(
                    "Add CreatedBy, CreatedDate, ModifiedBy, ModifiedDate columns to financial tables. "
                    "Populate them via DEFAULT constraints or triggers to maintain an immutable audit trail."
                ),
                line_number=1,
            )]
        return []


class SoxDirectDmlWithoutAuditRule(BaseRule):
    """SOX002 — Direct DML on a financial table without any audit logging pattern."""
    rule_id  = "SOX002"
    category = "Compliance-SOX"

    _DML_RE = re.compile(
        r'\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|DELETE)\s+', re.IGNORECASE
    )
    # Match INSERT INTO [schema.]table where table name contains audit/log/history/trail
    # Handles both plain names (LedgerAudit) and schema-qualified (dbo.LedgerAudit)
    _AUDIT_PATTERNS = [
        r'\bINSERT\s+INTO\s+(?:\[?\w+\]?\.)?\[?\w*audit\w*\]?\b',
        r'\bINSERT\s+INTO\s+(?:\[?\w+\]?\.)?\[?\w*log\w*\]?\b',
        r'\bINSERT\s+INTO\s+(?:\[?\w+\]?\.)?\[?\w*history\w*\]?\b',
        r'\bINSERT\s+INTO\s+(?:\[?\w+\]?\.)?\[?\w*trail\w*\]?\b',
    ]

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("Stored Procedure", "Trigger"):
            return []
        if not _is_financial_object(obj):
            return []
        src = self._safe_source(obj)
        has_dml = bool(self._DML_RE.search(src))
        if not has_dml:
            return []
        has_audit_log = any(
            re.search(p, src, re.IGNORECASE) for p in self._AUDIT_PATTERNS
        )
        if not has_audit_log:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue=(
                    f"Financial object '{obj.name}' performs DML without writing to an audit/log table"
                ),
                recommendation=(
                    "Every INSERT/UPDATE/DELETE on financial tables should be mirrored to an audit table "
                    "(e.g. <TableName>_Audit) with old/new values, timestamp, and the user principal."
                ),
                line_number=1,
            )]
        return []


class SoxXpCmdshellInFinancialRule(BaseRule):
    """SOX003 — xp_cmdshell or linked-server used inside a financial object."""
    rule_id  = "SOX003"
    category = "Compliance-SOX"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if not _is_financial_object(obj):
            return []
        findings = []
        src = self._safe_source(obj)
        for m in re.finditer(r'\bxp_cmdshell\b', src, re.IGNORECASE):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Critical",
                issue="xp_cmdshell detected in a financial object — violates SOX segregation of duties",
                recommendation="Remove xp_cmdshell from financial code paths. Use SQL Agent or application tier.",
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        # Four-part linked server names
        for m in re.finditer(r'\[\w+\]\.\[\w+\]\.\[\w+\]\.\[\w+\]', src):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="Linked server reference in financial object — data integrity risk under SOX",
                recommendation=(
                    "Linked server calls bypass local transaction control. "
                    "Use local replicated tables or service-layer APIs instead."
                ),
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class SoxGrantOnFinancialTableRule(BaseRule):
    """SOX004 — GRANT permission on a financial table — broad access risk."""
    rule_id  = "SOX004"
    category = "Compliance-SOX"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in re.finditer(
            r'\bGRANT\s+\w+\s+ON\s+(?:\[?\w+\]?\.)?\[?(\w+)\]?\s+TO\b',
            src, re.IGNORECASE,
        ):
            table_name = m.group(1)
            if _FINANCIAL_KEYWORDS.search(table_name):
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="High",
                    issue=f"GRANT permission on financial table '{table_name}' — review access control",
                    recommendation=(
                        "SOX requires least-privilege access. Access to financial tables should be "
                        "granted only through stored procedures, never directly to end users or roles."
                    ),
                    line_number=ln,
                    snippet=self.snippet_at(obj.source_lines, ln),
                ))
        return findings


class SoxNoErrorHandlingInTransactionRule(BaseRule):
    """SOX005 — Financial procedure has transaction but no TRY/CATCH error handling."""
    rule_id  = "SOX005"
    category = "Compliance-SOX"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("Stored Procedure", "Trigger"):
            return []
        if not _is_financial_object(obj):
            return []
        src = self._safe_source(obj)
        has_tran = bool(re.search(r'\bBEGIN\s+TRAN(SACTION)?\b', src, re.IGNORECASE))
        if not has_tran:
            return []
        has_try = bool(re.search(r'\bBEGIN\s+TRY\b', src, re.IGNORECASE))
        if not has_try:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue=(
                    f"Financial procedure '{obj.name}' uses transactions without TRY/CATCH error handling"
                ),
                recommendation=(
                    "Wrap all financial transactions in BEGIN TRY … BEGIN CATCH. "
                    "In the CATCH block: ROLLBACK TRANSACTION, log the error, and re-raise."
                ),
                line_number=1,
            )]
        return []


class SoxHardcodedFinancialValueRule(BaseRule):
    """SOX006 — Hardcoded monetary or percentage constant in financial code."""
    rule_id  = "SOX006"
    category = "Compliance-SOX"

    # Pattern: numeric literal that looks like a rate or fixed amount adjacent to financial columns
    _RATE_RE = re.compile(
        r'\b(tax_?rate|gst|vat|interest_?rate|commission)\s*[=<>!]+\s*(\d+\.?\d*)\b',
        re.IGNORECASE,
    )

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if not _is_financial_object(obj):
            return []
        findings = []
        src = self._safe_source(obj)
        for m in self._RATE_RE.finditer(src):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue=(
                    f"Hardcoded financial rate/constant '{m.group(0)}' detected "
                    "— rate changes require code deployments"
                ),
                recommendation=(
                    "Store tax rates, interest rates, and commission percentages in a configuration "
                    "or reference table. Hard-coded values create audit and change-management risks."
                ),
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


SOX_RULES: List[BaseRule] = [
    SoxMissingAuditColumnsRule(),
    SoxDirectDmlWithoutAuditRule(),
    SoxXpCmdshellInFinancialRule(),
    SoxGrantOnFinancialTableRule(),
    SoxNoErrorHandlingInTransactionRule(),
    SoxHardcodedFinancialValueRule(),
]
