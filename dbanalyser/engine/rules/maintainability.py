"""Maintainability rules — code complexity, length, magic numbers, dead code."""

from __future__ import annotations
import re
from typing import List
from .base import BaseRule, RuleFinding, SQLObject

# Complexity threshold constants
_MAX_LINES          = 500    # SP/trigger longer than this is a smell
_MAX_NESTED_LEVELS  = 4      # more than 4 levels of BEGIN…END nesting
_MAX_PARAMS         = 15     # excessive number of parameters


class LongProcedureRule(BaseRule):
    rule_id  = "MNT001"
    category = "Maintainability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("Stored Procedure", "Trigger", "Function"):
            return []
        if obj.lines > _MAX_LINES:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue=f"Object has {obj.lines} lines — exceeds {_MAX_LINES}-line threshold",
                recommendation=(
                    "Break the procedure into smaller, single-responsibility units. "
                    "Long procedures are hard to test and maintain."
                ),
                line_number=1,
            )]
        return []


class DeepNestingRule(BaseRule):
    """More than _MAX_NESTED_LEVELS of BEGIN … END blocks."""
    rule_id  = "MNT002"
    category = "Maintainability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        src = obj.source
        depth = 0
        max_depth = 0
        max_line  = 1
        line = 1
        i = 0
        while i < len(src):
            ch = src[i]
            if ch == "\n":
                line += 1
            # Simple tokeniser: look for BEGIN / END keywords
            if src[i:i+5].upper() == "BEGIN" and (
                    i == 0 or not src[i-1].isalnum()):
                # Ignore BEGIN TRY / BEGIN CATCH labels (still count)
                depth += 1
                if depth > max_depth:
                    max_depth = depth
                    max_line  = line
                i += 5
                continue
            if src[i:i+3].upper() == "END" and (
                    i == 0 or not src[i-1].isalnum()) and (
                    i + 3 >= len(src) or not src[i+3].isalnum()):
                depth = max(0, depth - 1)
                i += 3
                continue
            i += 1
        if max_depth > _MAX_NESTED_LEVELS:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue=f"Nesting depth of {max_depth} detected — deeply nested logic is hard to follow",
                recommendation=(
                    "Refactor deeply nested IF/WHILE blocks into helper procedures "
                    "or use early-return (RETURN) patterns."
                ),
                line_number=max_line,
            )]
        return []


class ExcessiveParametersRule(BaseRule):
    rule_id  = "MNT003"
    category = "Maintainability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("Stored Procedure", "Function"):
            return []
        # Count @param declarations in the header (before AS)
        header = obj.source[:2000]  # first 2 KB is enough for the signature
        params = re.findall(r'@\w+', header)
        # deduplicate by name
        unique = set(p.upper() for p in params)
        if len(unique) > _MAX_PARAMS:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue=f"Procedure has ~{len(unique)} parameters — exceeds {_MAX_PARAMS}-param guideline",
                recommendation=(
                    "Group related parameters into a structured type (TVP) or JSON/XML input "
                    "to reduce the surface area."
                ),
                line_number=1,
            )]
        return []


class MagicNumberRule(BaseRule):
    """Numeric literals used directly in WHERE / business logic (not 0 or 1)."""
    rule_id  = "MNT004"
    category = "Maintainability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        # Numbers that appear in WHERE or HAVING clauses, not 0/1/-1
        for m in self.find_pattern(
                r'\b(?:WHERE|HAVING|AND|OR)\b[^;\n]*\b(-?\d{2,})\b',
                src, re.IGNORECASE):
            num = m.group(1)
            if num in ("10", "100", "1000"):  # common non-magic constants
                continue
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue=f"Magic number {num} in business logic — meaning is unclear",
                recommendation=(
                    f"Replace {num} with a named variable or constant "
                    "(e.g., DECLARE @MaxRetryCount INT = {num}) for readability."
                ),
                line_number=ln,
            ))
        return findings[:5]


class CommentedOutCodeRule(BaseRule):
    """Large blocks of commented-out SQL — dead code clutters the object."""
    rule_id  = "MNT005"
    category = "Maintainability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = obj.source
        # Multi-line /* … */ comments that contain SELECT/INSERT/UPDATE
        for m in re.finditer(r'/\*.*?\*/', src, re.DOTALL):
            block = m.group()
            if re.search(r'\b(SELECT|INSERT|UPDATE|DELETE)\b', block, re.IGNORECASE):
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Low",
                    issue="Commented-out DML code found — dead code in production objects",
                    recommendation="Remove commented-out code blocks; use source control for history.",
                    line_number=ln,
                ))
        # Consecutive -- comment lines containing DML (≥3 lines)
        consecutive = 0
        first_line  = 0
        has_dml     = False
        for i, line in enumerate(obj.source_lines, start=1):
            stripped = line.strip()
            if stripped.startswith("--"):
                if re.search(r'\b(SELECT|INSERT|UPDATE|DELETE)\b', stripped, re.IGNORECASE):
                    has_dml = True
                if consecutive == 0:
                    first_line = i
                consecutive += 1
            else:
                if consecutive >= 3 and has_dml:
                    findings.append(RuleFinding(
                        rule_id=self.rule_id, category=self.category,
                        severity="Low",
                        issue=f"{consecutive} consecutive comment lines with DML — likely commented-out code",
                        recommendation="Remove dead code blocks; rely on source control for history.",
                        line_number=first_line,
                    ))
                consecutive = 0
                has_dml = False
        return findings[:3]


class HardcodedServerNameRule(BaseRule):
    """Server / database names hard-coded in USE or four-part names."""
    rule_id  = "MNT006"
    category = "Maintainability"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(r'^\s*USE\s+(\[?\w+\]?)', src,
                                    re.IGNORECASE | re.MULTILINE):
            db = m.group(1).strip("[]")
            if db.upper() not in ("MASTER", "TEMPDB"):
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Low",
                    issue=f"Hard-coded USE [{db}] — ties object to a specific database name",
                    recommendation=(
                        "Remove USE statements from stored objects. "
                        "Deploy objects into the correct database instead."
                    ),
                    line_number=ln,
                ))
        return findings


MAINTAINABILITY_RULES: List[BaseRule] = [
    LongProcedureRule(),
    DeepNestingRule(),
    ExcessiveParametersRule(),
    MagicNumberRule(),
    CommentedOutCodeRule(),
    HardcodedServerNameRule(),
]
