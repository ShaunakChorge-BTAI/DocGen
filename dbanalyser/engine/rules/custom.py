"""
Custom Rules Engine — YAML-Driven Rules
========================================
Define SQL analysis rules in YAML without writing Python code.

Rule file format (YAML):
  rules:
    - id: CUSTOM001
      name: "No direct SELECT from SensitiveTable"
      category: Security
      severity: High
      pattern: "SELECT.*FROM.*SensitiveTable"
      flags: IGNORECASE          # optional: IGNORECASE, MULTILINE, DOTALL (comma-separated)
      message: "Direct access to SensitiveTable is not allowed"
      recommendation: "Use the approved view vw_SensitiveData instead"
      object_types: []           # [] = all types; or ["Stored Procedure", "View"]
      enabled: true

Place rule files in:
  - The directory configured by custom_rules.rules_dir  (all *.yaml / *.yml files)
  - Or explicit paths listed in custom_rules.rules_files

Example:
  custom_rules:
    enabled: true
    rules_dir: ./custom_rules
    rules_files: []
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

import yaml

from .base import BaseRule, RuleFinding, SQLObject

log = logging.getLogger(__name__)

_VALID_SEVERITIES = {"Critical", "High", "Medium", "Low", "Info"}


# ─── YAML-backed rule class ────────────────────────────────────────────────────

class YamlRule(BaseRule):
    """A rule dynamically loaded from a YAML definition file."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        category: str,
        severity: str,
        pattern: str,
        message: str,
        recommendation: str,
        flags: int = re.IGNORECASE,
        object_types: List[str] | None = None,
        enabled: bool = True,
    ) -> None:
        self.rule_id        = rule_id
        self.name           = name
        self.category       = category
        self.severity       = severity
        self._pattern_str   = pattern
        self._message       = message
        self._recommendation = recommendation
        self._regex         = re.compile(pattern, flags)
        self._object_types  = [t.lower() for t in (object_types or [])]
        self.enabled        = enabled

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if not self.enabled:
            return []
        # Filter by object type if specified
        if self._object_types and obj.obj_type.lower() not in self._object_types:
            return []

        findings: List[RuleFinding] = []
        for i, line in enumerate(obj.source_lines, 1):
            if self._regex.search(line):
                findings.append(RuleFinding(
                    rule_id        = self.rule_id,
                    category       = self.category,
                    severity       = self.severity,
                    issue          = self._message,
                    recommendation = self._recommendation,
                    line_number    = i,
                    snippet        = line.strip()[:200],
                ))
        return findings


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_flags(flags_str: str) -> int:
    """Parse comma-separated flag names (IGNORECASE, MULTILINE, DOTALL) into re.* int."""
    result = 0
    for flag in [f.strip().upper() for f in (flags_str or "IGNORECASE").split(",")]:
        if flag in ("IGNORECASE", "I"):
            result |= re.IGNORECASE
        elif flag in ("MULTILINE", "M"):
            result |= re.MULTILINE
        elif flag in ("DOTALL", "S"):
            result |= re.DOTALL
    return result or re.IGNORECASE


# ─── Loaders ──────────────────────────────────────────────────────────────────

def load_rules_from_file(path: str | Path) -> List[YamlRule]:
    """Load all custom rules from a single YAML file.  Returns [] on error."""
    p = Path(path)
    if not p.exists():
        log.warning("Custom rules file not found: %s", p)
        return []
    try:
        with open(p, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:
        log.error("Failed to parse custom rules file %s: %s", p, exc)
        return []

    rules: List[YamlRule] = []
    for raw in data.get("rules", []):
        try:
            rule_id        = str(raw["id"])
            name           = str(raw.get("name", rule_id))
            category       = str(raw.get("category", "Custom"))
            severity       = str(raw.get("severity", "Medium"))
            if severity not in _VALID_SEVERITIES:
                log.warning("Rule %s has unknown severity '%s' — defaulting to Medium",
                            rule_id, severity)
                severity = "Medium"
            pattern        = str(raw["pattern"])
            message        = str(raw.get("message", f"Pattern matched: {pattern}"))
            recommendation = str(raw.get("recommendation", "Review this pattern."))
            flags_str      = str(raw.get("flags", "IGNORECASE"))
            flags          = _parse_flags(flags_str)
            object_types   = list(raw.get("object_types") or [])
            enabled        = bool(raw.get("enabled", True))

            rules.append(YamlRule(
                rule_id        = rule_id,
                name           = name,
                category       = category,
                severity       = severity,
                pattern        = pattern,
                message        = message,
                recommendation = recommendation,
                flags          = flags,
                object_types   = object_types,
                enabled        = enabled,
            ))
            log.debug("Loaded custom rule %s from %s", rule_id, p.name)

        except KeyError as exc:
            log.warning("Skipping malformed rule in %s — missing required field: %s", p, exc)
        except re.error as exc:
            log.warning("Skipping rule with invalid regex in %s: %s", p, exc)

    log.info("Loaded %d custom rule(s) from %s", len(rules), p.name)
    return rules


def load_custom_rules(cfg_custom) -> List[YamlRule]:
    """
    Load all custom YAML rules based on the CustomRulesConfig.

    Scans ``cfg_custom.rules_dir`` for *.yaml / *.yml files (recursive),
    then loads any explicit paths from ``cfg_custom.rules_files``.

    Args:
        cfg_custom: CustomRulesConfig instance from Settings.

    Returns:
        List of YamlRule instances ready for the rule engine.
    """
    if not getattr(cfg_custom, "enabled", False):
        return []

    all_rules: List[YamlRule] = []

    # ── scan directory ────────────────────────────────────────────────────────
    rules_dir = getattr(cfg_custom, "rules_dir", "./custom_rules")
    if rules_dir:
        d = Path(rules_dir)
        if d.is_dir():
            for yaml_file in sorted(list(d.rglob("*.yaml")) + list(d.rglob("*.yml"))):
                all_rules.extend(load_rules_from_file(yaml_file))
        else:
            log.debug("Custom rules dir not found (skipping): %s", d)

    # ── explicit files ────────────────────────────────────────────────────────
    for fpath in getattr(cfg_custom, "rules_files", []):
        all_rules.extend(load_rules_from_file(fpath))

    log.info("Total custom YAML rules loaded: %d", len(all_rules))
    return all_rules
