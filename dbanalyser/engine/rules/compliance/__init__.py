"""
Compliance Rule Pack Registry
==============================
Import individual packs and expose a registry keyed by pack name.

Usage
-----
    from dbanalyser.engine.rules.compliance import get_compliance_rules

    rules = get_compliance_rules(["sox", "gdpr"])   # list[BaseRule]
"""

from __future__ import annotations

from typing import Dict, List

from dbanalyser.engine.rules.base import BaseRule

from .sox  import SOX_RULES
from .gdpr import GDPR_RULES
from .rbi  import RBI_RULES

# Registry: lower-case pack name → rule list
_PACK_REGISTRY: Dict[str, List[BaseRule]] = {
    "sox":  SOX_RULES,
    "gdpr": GDPR_RULES,
    "rbi":  RBI_RULES,
}

COMPLIANCE_PACKS = list(_PACK_REGISTRY.keys())


def get_compliance_rules(enabled_packs: List[str]) -> List[BaseRule]:
    """
    Return the combined list of compliance rules for the given pack names.

    Parameters
    ----------
    enabled_packs : list of str
        Pack identifiers, e.g. ["sox", "gdpr"].  Unknown names are silently skipped.

    Returns
    -------
    list[BaseRule]
        Flat list of all enabled compliance rule instances.
    """
    rules: List[BaseRule] = []
    for pack in enabled_packs:
        pack_rules = _PACK_REGISTRY.get(pack.lower())
        if pack_rules:
            rules.extend(pack_rules)
    return rules


__all__ = [
    "SOX_RULES",
    "GDPR_RULES",
    "RBI_RULES",
    "COMPLIANCE_PACKS",
    "get_compliance_rules",
]
