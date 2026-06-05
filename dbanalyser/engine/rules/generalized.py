"""Generalized Rules — applicable to all SQL dialects (MSSQL, Postgres, MySQL, Oracle)."""
import re
from typing import List
from .base import BaseRule, RuleFinding, SQLObject

class UniversalSelectStarRule(BaseRule):
    """Flags SELECT * which is bad practice in any database."""
    rule_id  = "UNI001"
    category = "Performance"
    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(r'\bSELECT\s+\*', src):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category, severity="High",
                issue="SELECT * used — fetches all columns unnecessarily.",
                recommendation="Replace with explicit column names to reduce memory/network overhead.",
                line_number=ln
            ))
        return findings

class UniversalMissingWhereDeleteRule(BaseRule):
    """Flags DELETE statements missing a WHERE clause."""
    rule_id  = "UNI002"
    category = "Data Safety"
    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(r'\bDELETE\s+(?:FROM\s+)?[\w\.]+\b', src):
            block = src[m.start(): m.start() + 1000]
            if not re.search(r'\bWHERE\b', block, re.IGNORECASE):
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category, severity="Critical",
                    issue="DELETE statement has no WHERE clause.",
                    recommendation="Always include a WHERE clause or use TRUNCATE if you intend to empty the table.",
                    line_number=ln
                ))
        return findings

class UniversalHardcodedSecretRule(BaseRule):
    """Detects hardcoded passwords or API keys in the code."""
    rule_id  = "UNI003"
    category = "Security"
    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        pattern = r"(?i)(password|passwd|api_key|secret|token)\s*[=:]\s*['\"][^'\"]{4,}['\"]"
        for m in re.finditer(pattern, obj.source):
            ln = self.line_of(m, obj.source)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category, severity="Critical",
                issue="Hardcoded credential or secret detected in database code.",
                recommendation="Use external configuration or credential vaults.",
                line_number=ln
            ))
        return findings

class UniversalEmptyCatchBlockRule(BaseRule):
    """Detects empty EXCEPTION or CATCH blocks (swallowed errors)."""
    rule_id  = "UNI004"
    category = "Reliability"
    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        # Matches empty BEGIN CATCH ... END CATCH or EXCEPTION WHEN ... THEN END
        for m in self.find_pattern(r'\b(CATCH|EXCEPTION)\b[\s\n]*(END\b|WHEN\s+OTHERS\s+THEN\s+END\b)', src):
            # Avoid matching END CATCH followed by END (false positive)
            pre_text = src[:m.start()].rstrip()
            if pre_text.lower().endswith("end"):
                continue
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category, severity="High",
                issue="Empty exception/catch block detected.",
                recommendation="Never silently swallow errors. Always log them or re-raise the exception.",
                line_number=ln
            ))
        return findings

GENERALIZED_RULES = [
    UniversalSelectStarRule(),
    UniversalMissingWhereDeleteRule(),
    UniversalHardcodedSecretRule(),
    UniversalEmptyCatchBlockRule()
]

