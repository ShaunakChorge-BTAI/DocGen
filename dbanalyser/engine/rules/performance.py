"""Performance rules — SELECT *, implicit conversions, missing indexes, etc."""

from __future__ import annotations
import re
from typing import List
from .base import BaseRule, RuleFinding, SQLObject


class SelectStarRule(BaseRule):
    rule_id  = "PERF001"
    category = "Performance"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(r'\bSELECT\s+\*', src):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="SELECT * used — fetches all columns unnecessarily",
                recommendation="Replace with an explicit column list to reduce I/O and prevent breakage when the table schema changes.",
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class MissingNoCountRule(BaseRule):
    rule_id  = "PERF002"
    category = "Performance"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Stored Procedure":
            return []
        if not re.search(r'\bSET\s+NOCOUNT\s+ON\b', obj.source, re.IGNORECASE):
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue="Missing SET NOCOUNT ON — extra rowcount messages sent to client on every DML",
                recommendation="Add `SET NOCOUNT ON;` at the top of every stored procedure.",
                line_number=1,
            )]
        return []


class ImplicitConversionRule(BaseRule):
    rule_id  = "PERF003"
    category = "Performance"

    # VARCHAR/NVARCHAR literal used in WHERE against numeric column (heuristic)
    _PATTERNS = [
        (r"WHERE\s+\w+\s*=\s*N?'[^']*'", "String literal compared to likely numeric column"),
        (r"JOIN\s+\S+\s+ON\s+\S+\.\S+\s*=\s*\S+\.\S+", None),  # handled in extended
    ]

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        # CONVERT / CAST in JOIN ON clause hints at implicit conversion
        for m in self.find_pattern(r'\bJOIN\b[^;]+\bON\b[^;]+\b(CONVERT|CAST)\b', src, re.IGNORECASE | re.DOTALL):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="CONVERT/CAST in JOIN ON clause — may prevent index seek",
                recommendation="Ensure join columns have matching data types to avoid implicit conversions.",
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class NonSargableWhereRule(BaseRule):
    rule_id  = "PERF004"
    category = "Performance"

    _PATTERNS = [
        (r'\bWHERE\b[^;]+\bISNULL\s*\(\s*\w+', "ISNULL() in WHERE clause prevents index seek"),
        (r'\bWHERE\b[^;]+\bCONVERT\s*\(',       "CONVERT() in WHERE clause prevents index seek"),
        (r'\bWHERE\b[^;]+\bCASTED?\s*\(',        "CAST in WHERE clause prevents index seek"),
        (r'\bWHERE\b[^;]+\b\w+\s*\+\s*\w+\s*=', "Column arithmetic in WHERE prevents index seek"),
        (r"\bWHERE\b[^;]+\b\w+\s*LIKE\s*N?'%",  "Leading wildcard LIKE prevents index seek"),
    ]

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        # Use raw source for patterns that need to inspect string literal content
        # (e.g. LIKE '%...') and safe source for others
        src_safe = self._safe_source(obj)
        for pattern, desc in self._PATTERNS:
            # LIKE leading-wildcard check must run on raw source before strip_strings
            src = obj.source if "LIKE" in pattern else src_safe
            for m in self.find_pattern(pattern, src, re.IGNORECASE | re.DOTALL):
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="High",
                    issue=desc,
                    recommendation="Rewrite the WHERE clause to be SARGable (avoid functions on indexed columns).",
                    line_number=ln,
                    snippet=self.snippet_at(obj.source_lines, ln),
                ))
        return findings


class CursorUsageRule(BaseRule):
    rule_id  = "PERF005"
    category = "Performance"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(r'\bDECLARE\s+\w+\s+CURSOR\b', src):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="CURSOR used — row-by-row processing is orders of magnitude slower than set-based",
                recommendation="Rewrite using set-based operations (JOIN, UPDATE/DELETE with subquery, or window functions).",
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class NolockHintRule(BaseRule):
    rule_id  = "PERF006"
    category = "Performance"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        for m in self.find_pattern(r'\bWITH\s*\(\s*NOLOCK\s*\)', obj.source):
            ln = self.line_of(m, obj.source)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue="WITH(NOLOCK) hint used — may return dirty/uncommitted reads",
                recommendation="Use READ_COMMITTED_SNAPSHOT isolation instead. NOLOCK can return phantom rows or miss committed rows.",
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class MissingSchemaBindingRule(BaseRule):
    rule_id  = "PERF007"
    category = "Performance"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "View":
            return []
        if not re.search(r'\bWITH\s+SCHEMABINDING\b', obj.source, re.IGNORECASE):
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue="View does not use SCHEMABINDING — underlying tables can be modified without warning",
                recommendation="Add WITH SCHEMABINDING to prevent accidental schema changes that break the view.",
                line_number=1,
            )]
        return []


class DeprecatedSyntaxRule(BaseRule):
    rule_id  = "PERF008"
    category = "Performance"

    _PATTERNS = [
        (r'\*=',    "Deprecated *= outer join syntax (non-ANSI)"),
        (r'=\*',    "Deprecated =* outer join syntax (non-ANSI)"),
        (r'\b!<\b', "Deprecated !< comparison operator"),
        (r'\b!>\b', "Deprecated !> comparison operator"),
    ]

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        for pattern, desc in self._PATTERNS:
            for m in self.find_pattern(pattern, obj.source):
                ln = self.line_of(m, obj.source)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Medium",
                    issue=f"Deprecated syntax: {desc}",
                    recommendation="Replace with ANSI-standard JOIN / comparison syntax.",
                    line_number=ln,
                ))
        return findings


PERFORMANCE_RULES: List[BaseRule] = [
    SelectStarRule(),
    MissingNoCountRule(),
    ImplicitConversionRule(),
    NonSargableWhereRule(),
    CursorUsageRule(),
    NolockHintRule(),
    MissingSchemaBindingRule(),
    DeprecatedSyntaxRule(),
]
