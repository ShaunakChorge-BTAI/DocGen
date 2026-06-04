"""Security rules — SQL injection, hardcoded credentials, dynamic SQL."""

from __future__ import annotations
import re
from typing import List
from .base import BaseRule, RuleFinding, SQLObject


class DynamicSqlInjectionRule(BaseRule):
    rule_id  = "SEC001"
    category = "Security"

    _PATTERNS = [
        r"EXEC\s*\(\s*@\w+",
        r"EXEC\s*\(\s*N?'[^']*'\s*\+",     # EXEC('literal' + ...)
        r"EXEC\s*\(\s*@\w+\s*\+",           # EXEC(@var + ...)
        r"EXECUTE\s*\(\s*@\w+",
        r"EXECUTE\s*\(\s*N?'[^']*'\s*\+",   # EXECUTE('literal' + ...)
        r"EXECUTE\s*\(\s*@\w+\s*\+",        # EXECUTE(@var + ...)
        r"sp_executesql\s+@\w+\s*\+",
    ]

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        # String-concat patterns must run on raw source (safe_source strips the literal quotes)
        # Variable-exec patterns can use safe source (no string literals needed)
        src_raw  = obj.source
        src_safe = self._safe_source(obj)
        for pattern in self._PATTERNS:
            src = src_raw if ("N?'" in pattern) else src_safe
            for m in self.find_pattern(pattern, src):
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Critical",
                    issue="Potential SQL injection — dynamic SQL built by string concatenation",
                    recommendation="Use sp_executesql with strongly typed @params instead of string concatenation.",
                    line_number=ln,
                    snippet=self.snippet_at(obj.source_lines, ln),
                ))
        return findings


class HardcodedCredentialRule(BaseRule):
    rule_id  = "SEC002"
    category = "Security"

    _PATTERNS = [
        r"(?i)(password|passwd|pwd|secret|api_?key|apikey|token)\s*[=:]\s*N?'[^']{3,}'",
        r"(?i)(connectionstring|conn_?str)\s*=\s*N?'[^']*password\s*=",
        r"(?i)WITH\s+PASSWORD\s*=\s*N?'",
    ]

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        for pattern in self._PATTERNS:
            for m in re.finditer(pattern, obj.source):
                ln = self.line_of(m, obj.source)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Critical",
                    issue="Hardcoded credential or secret detected in SQL code",
                    recommendation="Move credentials to a secure vault (Azure Key Vault / encrypted config). Never store secrets in SQL objects.",
                    line_number=ln,
                ))
        return findings


class ExcessivePermissionsRule(BaseRule):
    rule_id  = "SEC003"
    category = "Security"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(r'\bGRANT\s+ALL\b', src):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="GRANT ALL permissions used — over-broad access grant",
                recommendation="Grant only specific permissions (SELECT, EXECUTE, etc.) rather than ALL.",
                line_number=ln,
            ))
        return findings


class LinkedServerRule(BaseRule):
    rule_id  = "SEC004"
    category = "Security"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        for m in self.find_pattern(r'\[\w+\]\.\[\w+\]\.\[\w+\]\.\[\w+\]', obj.source):
            ln = self.line_of(m, obj.source)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue="Four-part name (linked server) reference detected",
                recommendation="Linked server queries bypass local security context. Document and audit all cross-server references.",
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class XpCmdshellRule(BaseRule):
    rule_id  = "SEC005"
    category = "Security"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        for m in self.find_pattern(r'\bxp_cmdshell\b', obj.source):
            ln = self.line_of(m, obj.source)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Critical",
                issue="xp_cmdshell used — allows OS command execution from SQL",
                recommendation="Disable xp_cmdshell. Use SQL Agent jobs or application-layer code for OS operations.",
                line_number=ln,
            ))
        return findings


SECURITY_RULES: List[BaseRule] = [
    DynamicSqlInjectionRule(),
    HardcodedCredentialRule(),
    ExcessivePermissionsRule(),
    LinkedServerRule(),
    XpCmdshellRule(),
]
