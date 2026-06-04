"""Dangerous SQL rules — UPDATE/DELETE without WHERE, XACT_ABORT, trigger anti-patterns."""

from __future__ import annotations

import re
from typing import List

from .base import BaseRule, RuleFinding, SQLObject


class MissingWhereOnUpdateRule(BaseRule):
    """DNG001 — UPDATE statement without a WHERE clause."""
    rule_id  = "DNG001"
    category = "Data Safety"

    # Matches UPDATE <table-or-alias> SET ... without WHERE anywhere after SET
    # Strategy: find UPDATE…SET blocks, then check for absence of WHERE before
    # the next statement boundary (GO / ; / another DML keyword / END)
    _UPDATE_RE = re.compile(
        r'\bUPDATE\s+(?!STATISTICS\b)(?:\[?\w+\]?\.)*\[?\w+\]?\s+SET\b',
        re.IGNORECASE,
    )

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self._UPDATE_RE.finditer(src):
            block_start = m.start()
            # Look ahead up to 2000 chars for WHERE / FROM (join-style UPDATE)
            block = src[m.start(): m.start() + 2000]
            # Check for WHERE or statement terminator before WHERE
            has_where = bool(re.search(r'\bWHERE\b', block, re.IGNORECASE))
            # FROM clause with a join is acceptable (implicit filter via join)
            # but we still flag if there's genuinely no filter at all
            if not has_where:
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="High",
                    issue="UPDATE statement has no WHERE clause — will update every row in the table",
                    recommendation=(
                        "Always include a WHERE clause on UPDATE statements. "
                        "Consider wrapping in a transaction with row-count validation."
                    ),
                    line_number=ln,
                    snippet=self.snippet_at(obj.source_lines, ln),
                ))
        return findings


class MissingWhereOnDeleteRule(BaseRule):
    """DNG002 — DELETE statement without a WHERE clause."""
    rule_id  = "DNG002"
    category = "Data Safety"

    _DELETE_RE = re.compile(
        r'\bDELETE\s+(?:FROM\s+)?(?:\[?\w+\]?\.)*\[?\w+\]?\b',
        re.IGNORECASE,
    )

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self._DELETE_RE.finditer(src):
            block = src[m.start(): m.start() + 2000]
            has_where = bool(re.search(r'\bWHERE\b', block, re.IGNORECASE))
            if not has_where:
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="High",
                    issue="DELETE statement has no WHERE clause — will delete every row in the table",
                    recommendation=(
                        "Always include a WHERE clause on DELETE statements. "
                        "Use TRUNCATE TABLE only when full-table delete is intentional and audited."
                    ),
                    line_number=ln,
                    snippet=self.snippet_at(obj.source_lines, ln),
                ))
        return findings


class MissingXactAbortRule(BaseRule):
    """DNG003 — Procedure with explicit transactions but no SET XACT_ABORT ON."""
    rule_id  = "DNG003"
    category = "Reliability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("Stored Procedure", "Function", "Trigger"):
            return []
        src = self._safe_source(obj)
        has_transaction = bool(
            re.search(r'\bBEGIN\s+TRAN(SACTION)?\b', src, re.IGNORECASE)
        )
        if not has_transaction:
            return []
        has_xact_abort = bool(
            re.search(r'\bSET\s+XACT_ABORT\s+ON\b', src, re.IGNORECASE)
        )
        if not has_xact_abort:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="Procedure uses explicit transactions without SET XACT_ABORT ON",
                recommendation=(
                    "Add SET XACT_ABORT ON at the top of any routine that uses BEGIN TRAN. "
                    "Without it, a runtime error may leave a transaction open and cause blocking."
                ),
                line_number=1,
            )]
        return []


class TriggerCallingSpRule(BaseRule):
    """DNG004 — Trigger body invokes a stored procedure (side-effect anti-pattern)."""
    rule_id  = "DNG004"
    category = "Reliability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Trigger":
            return []
        findings = []
        src = self._safe_source(obj)
        for m in re.finditer(
            r'\b(EXEC|EXECUTE)\s+(?!sp_executesql\b)(?!\()(?:\[?\w+\]?\.)*\[?\w+\]?\b',
            src, re.IGNORECASE,
        ):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue="Trigger calls a stored procedure — triggers should not invoke SPs",
                recommendation=(
                    "Keep trigger logic minimal and inline. Calling stored procedures "
                    "from triggers creates hidden dependencies, makes debugging difficult, "
                    "and can cause performance issues under high DML load."
                ),
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class TriggerWithSelectStarRule(BaseRule):
    """DNG005 — SELECT * used inside a trigger body."""
    rule_id  = "DNG005"
    category = "Best Practices"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Trigger":
            return []
        findings = []
        src = self._safe_source(obj)
        for m in re.finditer(r'\bSELECT\s+\*', src, re.IGNORECASE):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue="SELECT * used inside trigger — fragile to schema changes",
                recommendation=(
                    "Explicitly list column names in trigger SELECT statements. "
                    "SELECT * breaks silently when columns are added or reordered."
                ),
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class RecursiveTriggerRiskRule(BaseRule):
    """DNG006 — Trigger performs DML on the same table it fires on (recursive trigger risk)."""
    rule_id  = "DNG006"
    category = "Reliability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Trigger":
            return []
        # Heuristic: extract the table name from the trigger name (usp_trg_TableName_*)
        # and check if any DML inside targets a table whose name appears in the trigger name
        src_upper = obj.source_upper
        # Look for ON <table> after CREATE TRIGGER
        tbl_match = re.search(
            r'\bON\s+(?:\[?\w+\]?\.)?\[?(\w+)\]?\b', obj.source, re.IGNORECASE
        )
        if not tbl_match:
            return []
        table_name = tbl_match.group(1).upper()
        # Check if there's an UPDATE/INSERT/DELETE targeting that same table in the body
        # (after the ON <table> line)
        body_start = tbl_match.end()
        body = src_upper[body_start:]
        dml_pattern = re.compile(
            rf'\b(UPDATE|INSERT\s+INTO|DELETE\s+FROM|DELETE)\s+(?:\[?\w+\]?\.)?{re.escape(table_name)}\b'
        )
        findings = []
        for m in dml_pattern.finditer(body):
            actual_pos = body_start + m.start()
            ln = obj.source_upper[:actual_pos].count("\n") + 1
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue=f"Trigger on '{table_name}' modifies the same table — potential infinite recursion",
                recommendation=(
                    "Check that 'recursive triggers' is disabled (ALTER DATABASE … RECURSIVE_TRIGGERS OFF). "
                    "If self-referencing is intentional, add a guard condition to prevent infinite loops."
                ),
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
            break   # one finding per trigger is enough
        return findings


DANGEROUS_SQL_RULES: List[BaseRule] = [
    MissingWhereOnUpdateRule(),
    MissingWhereOnDeleteRule(),
    MissingXactAbortRule(),
    TriggerCallingSpRule(),
    TriggerWithSelectStarRule(),
    RecursiveTriggerRiskRule(),
]
