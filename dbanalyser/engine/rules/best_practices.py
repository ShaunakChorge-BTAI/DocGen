"""Best practices rules — naming, schema prefix, SET options, etc."""

from __future__ import annotations
import re
from typing import List
from .base import BaseRule, RuleFinding, SQLObject


class MissingSchemaQualifierRule(BaseRule):
    rule_id  = "BP001"
    category = "Best Practices"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        # Unqualified table reference: FROM tableName without schema
        for m in self.find_pattern(
                r'\b(FROM|JOIN|INTO|UPDATE)\s+(?!\[?\w+\]?\.\[?\w+\]?)(\[?\w{3,}\]?)(?!\s*\()',
                src, re.IGNORECASE):
            name = m.group(2).strip("[]")
            # Skip keywords
            if name.upper() in ("SELECT","WHERE","SET","VALUES","OPENQUERY","OPENROWSET","DELETED","INSERTED"):
                continue
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue=f"Unqualified object reference '{name}' — no schema prefix",
                recommendation=f"Use schema-qualified names (e.g., dbo.{name}) to avoid ambiguity and prevent plan cache bloat.",
                line_number=ln,
            ))
        return findings[:10]  # cap at 10 per object


class MissingAnsiNullsRule(BaseRule):
    rule_id  = "BP002"
    category = "Best Practices"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if not re.search(r'\bSET\s+ANSI_NULLS\s+ON\b', obj.source, re.IGNORECASE):
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue="Missing SET ANSI_NULLS ON",
                recommendation="Add SET ANSI_NULLS ON at the top. Required for indexed views and some index operations.",
                line_number=1,
            )]
        return []


class MissingQuotedIdentifierRule(BaseRule):
    rule_id  = "BP003"
    category = "Best Practices"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if not re.search(r'\bSET\s+QUOTED_IDENTIFIER\s+ON\b', obj.source, re.IGNORECASE):
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue="Missing SET QUOTED_IDENTIFIER ON",
                recommendation="Add SET QUOTED_IDENTIFIER ON. Required for indexed views, XML indexes, and spatial indexes.",
                line_number=1,
            )]
        return []


class SpPrefixOnUserSpRule(BaseRule):
    rule_id  = "BP004"
    category = "Best Practices"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Stored Procedure":
            return []
        if obj.name.lower().startswith("sp_"):
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue="User SP named with 'sp_' prefix — reserved for system procedures",
                recommendation="Rename to remove 'sp_' prefix. SQL Server searches master.dbo first for sp_-prefixed names, causing unnecessary overhead.",
                line_number=1,
            )]
        return []


class OrderByWithoutTopRule(BaseRule):
    rule_id  = "BP005"
    category = "Best Practices"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        # Find ORDER BY not preceded by TOP / OFFSET / FOR XML
        for m in self.find_pattern(r'\bORDER\s+BY\b', src):
            preceding = src[max(0, m.start()-200):m.start()].upper()
            if "TOP" not in preceding and "OFFSET" not in preceding and "FOR" not in preceding:
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Low",
                    issue="ORDER BY without TOP/OFFSET — sort is ignored by the optimizer in subqueries and views",
                    recommendation="Remove ORDER BY from views/subqueries unless paired with TOP/OFFSET.",
                    line_number=ln,
                ))
        return findings[:5]


BEST_PRACTICE_RULES: List[BaseRule] = [
    MissingAnsiNullsRule(),
    MissingQuotedIdentifierRule(),
    SpPrefixOnUserSpRule(),
    OrderByWithoutTopRule(),
    MissingSchemaQualifierRule(),
]
