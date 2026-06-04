"""Parameter-sniffing rules — direct param use in WHERE, optional params, local vars."""

from __future__ import annotations
import re
from typing import List
from .base import BaseRule, RuleFinding, SQLObject


class DirectParamInWhereRule(BaseRule):
    """Detect @param used directly in WHERE that can cause plan reuse issues."""
    rule_id  = "PS001"
    category = "Parameter Sniffing"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("Stored Procedure", "Function"):
            return []
        findings = []
        src = self._safe_source(obj)
        # Find all declared params (top of proc)
        params = set(
            p.upper()
            for p in re.findall(r'@(\w+)', obj.source[:3000])
        )
        if not params:
            return []
        # Check if any param is used directly in a WHERE/HAVING clause
        for m in self.find_pattern(
                r'\b(?:WHERE|HAVING|AND|OR)\b[^;\n]*(@\w+)',
                src, re.IGNORECASE):
            pname = m.group(1).upper().lstrip("@")
            if pname in params:
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Medium",
                    issue=f"Parameter @{pname} used directly in WHERE — susceptible to parameter sniffing",
                    recommendation=(
                        f"Copy to a local variable: DECLARE @local_{pname} = @{pname}; "
                        "and use the local in the query to force per-execution plan compilation, "
                        "or add OPTION (RECOMPILE) / OPTION (OPTIMIZE FOR UNKNOWN)."
                    ),
                    line_number=ln,
                ))
        return findings[:5]


class OptionalParamAntipatternRule(BaseRule):
    """
    Detect the 'catch-all' optional-parameter anti-pattern:
    WHERE (@param IS NULL OR col = @param)
    This pattern forces a full table scan because a single plan must cover both cases.
    """
    rule_id  = "PS002"
    category = "Parameter Sniffing"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("Stored Procedure",):
            return []
        findings = []
        src = self._safe_source(obj)
        for m in self.find_pattern(
                r'(@\w+)\s+IS\s+NULL\s+OR\s+\w+\s*=\s*\1',
                src, re.IGNORECASE):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="Optional-parameter anti-pattern (@p IS NULL OR col = @p) — forces full scan",
                recommendation=(
                    "Use dynamic SQL with sp_executesql, or split into separate "
                    "code paths with IF @param IS NULL … ELSE …, and add OPTION (RECOMPILE)."
                ),
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class MissingRecompileHintRule(BaseRule):
    """
    Flag complex SPs with many parameters and no OPTION(RECOMPILE) or WITH RECOMPILE.
    These are likely to benefit from per-execution plans.
    """
    rule_id  = "PS003"
    category = "Parameter Sniffing"

    _MIN_PARAMS = 5   # only flag if the proc has several params

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Stored Procedure":
            return []
        src = obj.source
        param_count = len(set(re.findall(r'@\w+', src[:3000])))
        if param_count < self._MIN_PARAMS:
            return []
        has_recompile = bool(re.search(
            r'\b(?:WITH\s+RECOMPILE|OPTION\s*\(\s*RECOMPILE\s*\))', src, re.IGNORECASE))
        has_optimize  = bool(re.search(
            r'\bOPTION\s*\(\s*OPTIMIZE\s+FOR\b', src, re.IGNORECASE))
        if not has_recompile and not has_optimize:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue=(
                    f"SP with {param_count} parameters has no OPTION(RECOMPILE) or "
                    "OPTION(OPTIMIZE FOR …) hint — may be exposed to parameter sniffing"
                ),
                recommendation=(
                    "Consider adding OPTION (OPTIMIZE FOR UNKNOWN) to critical queries, "
                    "or WITH RECOMPILE on the procedure if data distribution is highly skewed."
                ),
                line_number=1,
            )]
        return []


class LocalVariableWorkaroundRule(BaseRule):
    """
    Detect where a local variable is assigned from a parameter and then used in WHERE.
    This is the *correct* workaround — flag as informational (Low) so teams know it's intentional.
    """
    rule_id  = "PS004"
    category = "Parameter Sniffing"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Stored Procedure":
            return []
        src = obj.source
        # DECLARE @local … SET @local = @param
        locals_from_params = re.findall(
            r'SET\s+(@\w+)\s*=\s*(@\w+)', src, re.IGNORECASE)
        if locals_from_params:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Low",
                issue=(
                    "Local variable(s) assigned from input parameters — "
                    "parameter-sniffing workaround detected"
                ),
                recommendation=(
                    "This is a known workaround for parameter sniffing. "
                    "Document why it is needed and consider OPTION (OPTIMIZE FOR UNKNOWN) "
                    "as a cleaner alternative."
                ),
                line_number=1,
            )]
        return []


PARAMETER_SNIFFING_RULES: List[BaseRule] = [
    DirectParamInWhereRule(),
    OptionalParamAntipatternRule(),
    MissingRecompileHintRule(),
    LocalVariableWorkaroundRule(),
]
