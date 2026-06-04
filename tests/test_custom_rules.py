"""
Tests for YAML-driven custom rules engine (dbanalyser/engine/rules/custom.py).
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

from dbanalyser.engine.rules.base import SQLObject
from dbanalyser.engine.rules.custom import (
    YamlRule,
    _parse_flags,
    load_rules_from_file,
    load_custom_rules,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _sp(source: str, name: str = "usp_Test") -> SQLObject:
    src = textwrap.dedent(source).strip()
    return SQLObject(
        name=name,
        obj_type="Stored Procedure",
        schema="dbo",
        source=src,
        source_lines=src.splitlines(),
    )


def _table(source: str, name: str = "TestTable") -> SQLObject:
    src = textwrap.dedent(source).strip()
    return SQLObject(
        name=name,
        obj_type="Table",
        schema="dbo",
        source=src,
        source_lines=src.splitlines(),
    )


# ─── YamlRule.analyse ────────────────────────────────────────────────────────

class TestYamlRuleAnalyse:
    def _rule(self, **kwargs) -> YamlRule:
        defaults = dict(
            rule_id="CUSTOM001",
            name="Test Rule",
            category="Custom",
            severity="High",
            pattern=r"SELECT\s+\*\s+FROM\s+SensitiveTable",
            message="Direct access to SensitiveTable",
            recommendation="Use vw_Masked instead",
        )
        defaults.update(kwargs)
        return YamlRule(**defaults)

    def test_match_returns_finding(self):
        rule = self._rule()
        obj  = _sp("SELECT * FROM SensitiveTable WHERE Id = @Id")
        findings = rule.analyse(obj)
        assert len(findings) == 1
        assert findings[0].rule_id == "CUSTOM001"
        assert findings[0].severity == "High"
        assert findings[0].category == "Custom"

    def test_no_match_returns_empty(self):
        rule = self._rule()
        obj  = _sp("SELECT Id, Name FROM SafeTable WHERE Id = @Id")
        assert rule.analyse(obj) == []

    def test_disabled_rule_skipped(self):
        rule = self._rule(enabled=False)
        obj  = _sp("SELECT * FROM SensitiveTable")
        assert rule.analyse(obj) == []

    def test_object_type_filter_excludes(self):
        rule = self._rule(object_types=["View"])
        obj  = _sp("SELECT * FROM SensitiveTable")  # Stored Procedure, not View
        assert rule.analyse(obj) == []

    def test_object_type_filter_includes(self):
        rule = self._rule(object_types=["Stored Procedure"])
        obj  = _sp("SELECT * FROM SensitiveTable")
        assert len(rule.analyse(obj)) == 1

    def test_case_insensitive_match(self):
        rule = self._rule(pattern=r"select\s+\*\s+from\s+sensitivetable",
                         flags=re.IGNORECASE)
        obj  = _sp("SELECT * FROM SENSITIVETABLE")
        assert len(rule.analyse(obj)) == 1

    def test_multiline_each_line_matched(self):
        rule = self._rule(pattern=r"SELECT\s+\*\s+FROM\s+SensitiveTable")
        obj  = _sp("""
            SELECT * FROM SensitiveTable
            WHERE Active = 1
            SELECT * FROM SensitiveTable
            WHERE Id = 2
        """)
        assert len(rule.analyse(obj)) == 2

    def test_snippet_truncated_to_200(self):
        long_line = "SELECT * FROM SensitiveTable WHERE " + "x" * 300
        rule     = self._rule()
        obj      = _sp(long_line)
        findings = rule.analyse(obj)
        assert len(findings) == 1
        assert len(findings[0].snippet) <= 200

    def test_line_number_reported(self):
        rule = self._rule()
        obj  = _sp("-- safe\n-- safe\nSELECT * FROM SensitiveTable")
        findings = rule.analyse(obj)
        assert len(findings) == 1
        assert findings[0].line_number == 3


# ─── _parse_flags ────────────────────────────────────────────────────────────

class TestParseFlags:
    def test_ignorecase(self):
        assert _parse_flags("IGNORECASE") & re.IGNORECASE

    def test_multiline(self):
        assert _parse_flags("MULTILINE") & re.MULTILINE

    def test_dotall(self):
        assert _parse_flags("DOTALL") & re.DOTALL

    def test_combined(self):
        flags = _parse_flags("IGNORECASE,MULTILINE")
        assert flags & re.IGNORECASE
        assert flags & re.MULTILINE

    def test_short_form_i(self):
        assert _parse_flags("I") & re.IGNORECASE

    def test_empty_defaults_to_ignorecase(self):
        assert _parse_flags("") & re.IGNORECASE

    def test_unknown_flag_defaults_to_ignorecase(self):
        flags = _parse_flags("UNKNOWN_FLAG")
        assert flags == re.IGNORECASE


# ─── load_rules_from_file ────────────────────────────────────────────────────

class TestLoadRulesFromFile:
    def test_load_valid_file(self, tmp_path: Path):
        yaml_content = """
rules:
  - id: TEST001
    name: Test Rule
    category: Security
    severity: High
    pattern: "EXEC\\\\s+xp_cmdshell"
    message: "xp_cmdshell detected"
    recommendation: "Remove xp_cmdshell usage"
"""
        f = tmp_path / "rules.yaml"
        f.write_text(yaml_content)
        rules = load_rules_from_file(f)
        assert len(rules) == 1
        assert rules[0].rule_id == "TEST001"
        assert rules[0].severity == "High"

    def test_missing_file_returns_empty(self, tmp_path: Path):
        rules = load_rules_from_file(tmp_path / "nonexistent.yaml")
        assert rules == []

    def test_missing_pattern_skips_rule(self, tmp_path: Path):
        yaml_content = """
rules:
  - id: NOPAT
    name: No Pattern
    severity: High
    message: "Missing pattern field"
"""
        f = tmp_path / "bad.yaml"
        f.write_text(yaml_content)
        rules = load_rules_from_file(f)
        assert rules == []   # should be skipped

    def test_invalid_regex_skips_rule(self, tmp_path: Path):
        yaml_content = """
rules:
  - id: BADRX
    pattern: "[invalid(("
    message: "Bad regex"
"""
        f = tmp_path / "bad_rx.yaml"
        f.write_text(yaml_content)
        rules = load_rules_from_file(f)
        assert rules == []

    def test_multiple_rules_loaded(self, tmp_path: Path):
        yaml_content = """
rules:
  - id: R001
    pattern: "PATTERN_A"
    message: "A"
  - id: R002
    pattern: "PATTERN_B"
    message: "B"
"""
        f = tmp_path / "multi.yaml"
        f.write_text(yaml_content)
        rules = load_rules_from_file(f)
        assert len(rules) == 2
        assert {r.rule_id for r in rules} == {"R001", "R002"}

    def test_disabled_rule_still_loaded(self, tmp_path: Path):
        yaml_content = """
rules:
  - id: DIS001
    pattern: "SOMETHING"
    message: "Disabled"
    enabled: false
"""
        f = tmp_path / "dis.yaml"
        f.write_text(yaml_content)
        rules = load_rules_from_file(f)
        assert len(rules) == 1
        assert rules[0].enabled is False


# ─── load_custom_rules ───────────────────────────────────────────────────────

class TestLoadCustomRules:
    def _cfg(self, enabled: bool, rules_dir: str = "", rules_files=None):
        class Cfg:
            pass
        c = Cfg()
        c.enabled     = enabled
        c.rules_dir   = rules_dir
        c.rules_files = rules_files or []
        return c

    def test_disabled_returns_empty(self):
        cfg = self._cfg(enabled=False, rules_dir="./custom_rules")
        assert load_custom_rules(cfg) == []

    def test_loads_from_dir(self, tmp_path: Path):
        yaml_content = """
rules:
  - id: DIR001
    pattern: "SOME_PATTERN"
    message: "Found it"
"""
        (tmp_path / "my_rules.yaml").write_text(yaml_content)
        cfg = self._cfg(enabled=True, rules_dir=str(tmp_path))
        rules = load_custom_rules(cfg)
        assert len(rules) == 1
        assert rules[0].rule_id == "DIR001"

    def test_loads_from_explicit_files(self, tmp_path: Path):
        f = tmp_path / "explicit.yaml"
        f.write_text("rules:\n  - id: EXP001\n    pattern: 'P'\n    message: 'M'\n")
        cfg = self._cfg(enabled=True, rules_dir="", rules_files=[str(f)])
        rules = load_custom_rules(cfg)
        assert any(r.rule_id == "EXP001" for r in rules)

    def test_nonexistent_dir_returns_empty(self):
        cfg = self._cfg(enabled=True, rules_dir="/nonexistent/path")
        rules = load_custom_rules(cfg)
        assert rules == []

    def test_integrated_with_build_rule_set(self, tmp_path: Path):
        """build_rule_set should include custom rules when enabled."""
        f = tmp_path / "custom.yaml"
        f.write_text("rules:\n  - id: INT001\n    pattern: 'DANGER'\n    message: 'Danger!'\n")

        from dbanalyser.engine.rules import build_rule_set

        class MockCustomCfg:
            enabled     = True
            rules_dir   = ""
            rules_files = [str(f)]

        class MockCfg:
            custom_rules = MockCustomCfg()
            compliance   = type("C", (), {"enabled_packs": []})()

        rules = build_rule_set(MockCfg())
        ids   = [r.rule_id for r in rules]
        assert "INT001" in ids
