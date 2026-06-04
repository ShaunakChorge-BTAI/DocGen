"""Reliability rules — TRY/CATCH, transaction handling, error propagation."""

from __future__ import annotations
import re
from typing import List
from .base import BaseRule, RuleFinding, SQLObject


class MissingTryCatchRule(BaseRule):
    rule_id  = "REL001"
    category = "Reliability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("Stored Procedure", "Trigger"):
            return []
        has_dml = bool(re.search(
            r'\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b',
            obj.source, re.IGNORECASE))
        if not has_dml:
            return []
        has_try = bool(re.search(r'\bBEGIN\s+TRY\b', obj.source, re.IGNORECASE))
        if not has_try:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="No TRY/CATCH block — DML errors will propagate unhandled to the caller",
                recommendation="Wrap DML statements in BEGIN TRY / BEGIN CATCH with ROLLBACK TRANSACTION in the CATCH block.",
                line_number=1,
            )]
        return []


class TransactionWithoutRollbackRule(BaseRule):
    rule_id  = "REL002"
    category = "Reliability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        src = obj.source_upper
        has_begin_tran = bool(re.search(r'\bBEGIN\s+(TRAN|TRANSACTION)\b', src))
        if not has_begin_tran:
            return []
        has_catch      = bool(re.search(r'\bBEGIN\s+CATCH\b', src))
        has_rollback   = bool(re.search(r'\bROLLBACK\b', src))
        if has_begin_tran and has_catch and not has_rollback:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="BEGIN TRANSACTION used with CATCH but no ROLLBACK — partial commits on error",
                recommendation="Add ROLLBACK TRANSACTION inside the CATCH block.",
                line_number=1,
            )]
        if has_begin_tran and not has_catch:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue="BEGIN TRANSACTION without TRY/CATCH — unhandled errors leave transactions open",
                recommendation="Wrap transaction in TRY/CATCH with ROLLBACK in the CATCH block.",
                line_number=1,
            )]
        return []


class RaiserrorInsteadOfThrowRule(BaseRule):
    rule_id  = "REL003"
    category = "Reliability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        for m in self.find_pattern(r'\bRAISERROR\b', obj.source):
            ln = self.line_of(m, obj.source)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue="RAISERROR used — consider THROW (SQL Server 2012+)",
                recommendation="THROW re-raises with original error number and is simpler. Use THROW unless targeting SQL 2008.",
                line_number=ln,
            ))
        return findings


class PrintInProductionRule(BaseRule):
    rule_id  = "REL004"
    category = "Reliability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(r'^\s*PRINT\s+', src, re.IGNORECASE | re.MULTILINE):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue="PRINT statement in production SP — debug output sent to client",
                recommendation="Remove PRINT statements before deploying to production. Use a logging table instead.",
                line_number=ln,
            ))
        return findings


RELIABILITY_RULES: List[BaseRule] = [
    MissingTryCatchRule(),
    TransactionWithoutRollbackRule(),
    RaiserrorInsteadOfThrowRule(),
    PrintInProductionRule(),
]
