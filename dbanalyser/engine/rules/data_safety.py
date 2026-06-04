"""Data-safety rules — NULL handling, implicit NULL comparisons, data truncation."""

from __future__ import annotations
import re
from typing import List
from .base import BaseRule, RuleFinding, SQLObject


class ImplicitNullComparisonRule(BaseRule):
    rule_id  = "DS001"
    category = "Data Safety"

    # SQL types that appear before = NULL in parameter default declarations
    _SQL_TYPES = frozenset({
        "INT","BIGINT","SMALLINT","TINYINT","BIT","FLOAT","REAL","DECIMAL","NUMERIC",
        "MONEY","SMALLMONEY","DATE","DATETIME","DATETIME2","SMALLDATETIME","TIME",
        "CHAR","VARCHAR","NCHAR","NVARCHAR","TEXT","NTEXT","BINARY","VARBINARY",
        "UNIQUEIDENTIFIER","XML","IMAGE","SYSNAME","SQL_VARIANT",
    })

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        # Detect  col = NULL  or  col <> NULL  (should be IS NULL / IS NOT NULL)
        for m in self.find_pattern(
                r'\b(\w+)\s*(?:=|<>|!=)\s*NULL\b', src, re.IGNORECASE):
            token = m.group(1).upper()
            # Skip SQL data-type names — these are parameter default declarations like
            #   @Param DATE = NULL  or  @Param INT = NULL
            if token in self._SQL_TYPES:
                continue
            # Also skip @variable = NULL assignments (those are initialisation, not comparison)
            preceding = src[max(0, m.start()-20):m.start()]
            if re.search(r'DECLARE\s+@\w+', preceding, re.IGNORECASE):
                continue
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="NULL comparison using = or <> — always evaluates to UNKNOWN",
                recommendation="Use IS NULL or IS NOT NULL to test for NULLs.",
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class NullableColumnInJoinRule(BaseRule):
    """Flag JOIN conditions that compare nullable columns without COALESCE/ISNULL guard."""
    rule_id  = "DS002"
    category = "Data Safety"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        # JOIN ON col1 = col2 where neither side wraps ISNULL/COALESCE — heuristic
        for m in self.find_pattern(
                r'\bON\b\s+(?!.*\b(?:ISNULL|COALESCE)\b)([^\n;]{5,80})',
                src, re.IGNORECASE):
            # Only flag if there is no function wrapper at all in the ON clause
            clause = m.group(1)
            if not re.search(r'\b(ISNULL|COALESCE|NULLIF)\b', clause, re.IGNORECASE):
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Low",
                    issue="JOIN ON clause may silently drop rows if columns are nullable",
                    recommendation=(
                        "Consider wrapping nullable join keys in ISNULL(col, default) "
                        "to make NULL-handling explicit."
                    ),
                    line_number=ln,
                ))
        return findings[:5]


class DataTruncationRiskRule(BaseRule):
    """Detect INSERT … SELECT or UPDATE … SET that may silently truncate strings."""
    rule_id  = "DS003"
    category = "Data Safety"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        # CONVERT(VARCHAR(n), …) with a small n is a truncation risk in assignments
        for m in self.find_pattern(
                r'\bCONVERT\s*\(\s*(?:VAR)?CHAR\s*\(\s*(\d+)\s*\)',
                src, re.IGNORECASE):
            n = int(m.group(1))
            if n < 50:
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Medium",
                    issue=f"CONVERT to (VAR)CHAR({n}) — small target size may silently truncate data",
                    recommendation=(
                        f"Verify the source column never exceeds {n} characters, "
                        "or widen the target type."
                    ),
                    line_number=ln,
                    snippet=self.snippet_at(obj.source_lines, ln),
                ))
        return findings[:10]


class SelectIntoWithoutSchemaRule(BaseRule):
    """SELECT … INTO #temp or new_table without schema qualifier."""
    rule_id  = "DS004"
    category = "Data Safety"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(
                r'\bSELECT\b.+?\bINTO\b\s+(\[?\w+\]?)\s',
                src, re.IGNORECASE | re.DOTALL):
            tbl = m.group(1).strip("[]")
            # temp tables are fine; flag permanent tables without schema
            if not tbl.startswith("#") and "." not in tbl:
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Medium",
                    issue=f"SELECT INTO '{tbl}' without schema — table lands in default schema",
                    recommendation=f"Use SELECT … INTO dbo.{tbl} to make the destination explicit.",
                    line_number=ln,
                ))
        return findings[:5]


class NullInNotInSubqueryRule(BaseRule):
    """NOT IN subquery that may contain NULLs — returns no rows silently."""
    rule_id  = "DS005"
    category = "Data Safety"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(r'\bNOT\s+IN\s*\(\s*SELECT\b', src, re.IGNORECASE):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="NOT IN (SELECT …) — if the subquery returns any NULL the whole predicate returns 0 rows",
                recommendation=(
                    "Use NOT EXISTS or add WHERE col IS NOT NULL inside the subquery "
                    "to guard against NULL contamination."
                ),
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class UnboundedVarcharRule(BaseRule):
    """VARCHAR(MAX) / NVARCHAR(MAX) used in a column definition or variable."""
    rule_id  = "DS006"
    category = "Data Safety"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(
                r'\b(?:N?VAR)?CHAR\s*\(\s*MAX\s*\)', src, re.IGNORECASE):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue="VARCHAR(MAX) / NVARCHAR(MAX) used — can cause row-overflow and performance issues",
                recommendation=(
                    "Prefer a bounded size (e.g., NVARCHAR(500)) unless truly variable-length "
                    "large text is required. MAX columns cannot be indexed directly."
                ),
                line_number=ln,
            ))
        return findings[:5]


DATA_SAFETY_RULES: List[BaseRule] = [
    ImplicitNullComparisonRule(),
    NullableColumnInJoinRule(),
    DataTruncationRiskRule(),
    SelectIntoWithoutSchemaRule(),
    NullInNotInSubqueryRule(),
    UnboundedVarcharRule(),
]
