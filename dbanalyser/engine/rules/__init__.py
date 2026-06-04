"""Rule registry — import all rule lists and expose ALL_RULES."""

from __future__ import annotations
from typing import List, Optional

from .base import BaseRule, RuleFinding, SQLObject
from .performance        import PERFORMANCE_RULES
from .security           import SECURITY_RULES
from .reliability        import RELIABILITY_RULES
from .best_practices     import BEST_PRACTICE_RULES
from .data_safety        import DATA_SAFETY_RULES
from .maintainability    import MAINTAINABILITY_RULES
from .parameter_sniffing import PARAMETER_SNIFFING_RULES
from .dangerous_sql      import DANGEROUS_SQL_RULES

from .generalized import GENERALIZED_RULES

ALL_RULES: List[BaseRule] = (
    GENERALIZED_RULES        +   # universal rules that apply to all databases
    SECURITY_RULES           +   # run security first (Critical items)
    RELIABILITY_RULES        +
    PERFORMANCE_RULES        +
    DATA_SAFETY_RULES        +
    DANGEROUS_SQL_RULES      +   # UPDATE/DELETE without WHERE, XACT_ABORT, trigger rules
    BEST_PRACTICE_RULES      +
    PARAMETER_SNIFFING_RULES +
    MAINTAINABILITY_RULES
)


def build_rule_set(cfg=None) -> List[BaseRule]:
    """
    Return the full rule set, optionally extended with compliance packs.

    Parameters
    ----------
    cfg : Settings | None
        If provided, compliance packs listed in ``cfg.compliance.enabled_packs``
        are appended to the base rule set.
    """
    rules = list(ALL_RULES)
    if cfg is None:
        return rules
    try:
        enabled_packs = getattr(getattr(cfg, "compliance", None), "enabled_packs", [])
        if enabled_packs:
            from .compliance import get_compliance_rules
            rules.extend(get_compliance_rules(enabled_packs))
    except Exception:
        pass
    try:
        custom_cfg = getattr(cfg, "custom_rules", None)
        if custom_cfg and getattr(custom_cfg, "enabled", False):
            from .custom import load_custom_rules
            rules.extend(load_custom_rules(custom_cfg))
    except Exception:
        pass
    return rules


__all__ = [
    "BaseRule", "RuleFinding", "SQLObject",
    "ALL_RULES",
    "PERFORMANCE_RULES", "SECURITY_RULES", "RELIABILITY_RULES",
    "BEST_PRACTICE_RULES", "DATA_SAFETY_RULES",
    "MAINTAINABILITY_RULES", "PARAMETER_SNIFFING_RULES",
    "DANGEROUS_SQL_RULES",
    "build_rule_set",
]
