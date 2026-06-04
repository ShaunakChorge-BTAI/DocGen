"""
Unit tests — dangerous_sql rule pack (DNG001 – DNG006).

Run with:
    cd D:\\LTFS\\ltfs-analyzer
    python -m pytest tests/test_dangerous_sql.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from dbanalyser.engine.rules.base import SQLObject
from dbanalyser.engine.rules.dangerous_sql import (
    MissingWhereOnUpdateRule,
    MissingWhereOnDeleteRule,
    MissingXactAbortRule,
    TriggerCallingSpRule,
    TriggerWithSelectStarRule,
    RecursiveTriggerRiskRule,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _sp(source: str, name: str = "TestProc") -> SQLObject:
    return SQLObject(name=name, obj_type="Stored Procedure",
                     schema="dbo", source=source)


def _trigger(source: str, name: str = "trg_Orders_AI") -> SQLObject:
    return SQLObject(name=name, obj_type="Trigger",
                     schema="dbo", source=source)


def _view(source: str) -> SQLObject:
    return SQLObject(name="TestView", obj_type="View",
                     schema="dbo", source=source)


# ── DNG001 — UPDATE without WHERE ─────────────────────────────────────────────

class TestMissingWhereOnUpdateRule:
    rule = MissingWhereOnUpdateRule()

    def test_detects_update_without_where(self):
        obj = _sp("UPDATE dbo.Orders SET Status = 1")
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert findings[0].severity == "High"
        assert "WHERE" in findings[0].issue

    def test_update_statistics_ignored(self):
        obj = _sp("UPDATE STATISTICS dbo.Orders")
        assert self.rule.analyse(obj) == []

    def test_no_finding_with_where(self):
        obj = _sp("UPDATE dbo.Orders SET Status = 1 WHERE OrderId = @Id")
        assert self.rule.analyse(obj) == []

    def test_no_finding_on_view(self):
        obj = _view("SELECT 1")
        assert self.rule.analyse(obj) == []


# ── DNG002 — DELETE without WHERE ─────────────────────────────────────────────

class TestMissingWhereOnDeleteRule:
    rule = MissingWhereOnDeleteRule()

    def test_detects_delete_without_where(self):
        obj = _sp("DELETE FROM dbo.StagingTable")
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert findings[0].severity == "High"
        assert "WHERE" in findings[0].issue

    def test_no_finding_with_where(self):
        obj = _sp("DELETE FROM dbo.Orders WHERE OrderDate < '2000-01-01'")
        assert self.rule.analyse(obj) == []

    def test_delete_shorthand_without_where(self):
        obj = _sp("DELETE dbo.Logs")
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1


# ── DNG003 — Missing XACT_ABORT ───────────────────────────────────────────────

class TestMissingXactAbortRule:
    rule = MissingXactAbortRule()

    def test_detects_missing_xact_abort(self):
        obj = _sp("""
            CREATE PROCEDURE dbo.DoWork AS
            BEGIN
                BEGIN TRANSACTION;
                INSERT INTO dbo.T VALUES(1);
                COMMIT TRANSACTION;
            END
        """)
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert "XACT_ABORT" in findings[0].issue

    def test_no_finding_when_set(self):
        obj = _sp("""
            CREATE PROCEDURE dbo.DoWork AS
            BEGIN
                SET XACT_ABORT ON;
                BEGIN TRANSACTION;
                INSERT INTO dbo.T VALUES(1);
                COMMIT TRANSACTION;
            END
        """)
        assert self.rule.analyse(obj) == []

    def test_no_finding_without_transaction(self):
        """Procedures without explicit transactions don't need XACT_ABORT."""
        obj = _sp("CREATE PROCEDURE dbo.DoWork AS SELECT 1")
        assert self.rule.analyse(obj) == []

    def test_skips_view(self):
        obj = _view("SELECT 1")
        assert self.rule.analyse(obj) == []


# ── DNG004 — Trigger calling stored procedure ─────────────────────────────────

class TestTriggerCallingSpRule:
    rule = TriggerCallingSpRule()

    def test_detects_exec_in_trigger(self):
        src = """
            CREATE TRIGGER trg_Orders_AI ON dbo.Orders AFTER INSERT AS
            BEGIN
                EXEC dbo.usp_SendNotification;
            END
        """
        obj = _trigger(src)
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert "stored procedure" in findings[0].issue.lower()

    def test_no_finding_on_sp(self):
        obj = _sp("EXEC dbo.usp_Helper")
        assert self.rule.analyse(obj) == []

    def test_no_finding_for_sp_executesql(self):
        src = """
            CREATE TRIGGER trg_T ON dbo.T AFTER INSERT AS
            BEGIN
                EXEC sp_executesql @sql;
            END
        """
        obj = _trigger(src)
        # sp_executesql is explicitly excluded
        assert self.rule.analyse(obj) == []


# ── DNG005 — SELECT * in trigger ─────────────────────────────────────────────

class TestTriggerWithSelectStarRule:
    rule = TriggerWithSelectStarRule()

    def test_detects_select_star_in_trigger(self):
        src = """
            CREATE TRIGGER trg_T ON dbo.T AFTER INSERT AS
            BEGIN
                SELECT * FROM inserted;
            END
        """
        obj = _trigger(src)
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert "SELECT *" in findings[0].issue

    def test_no_finding_on_explicit_columns(self):
        src = """
            CREATE TRIGGER trg_T ON dbo.T AFTER INSERT AS
            BEGIN
                SELECT Id, Name FROM inserted;
            END
        """
        obj = _trigger(src)
        assert self.rule.analyse(obj) == []

    def test_skips_stored_procedure(self):
        obj = _sp("SELECT * FROM dbo.T")
        assert self.rule.analyse(obj) == []


# ── DNG006 — Recursive trigger risk ──────────────────────────────────────────

class TestRecursiveTriggerRiskRule:
    rule = RecursiveTriggerRiskRule()

    def test_detects_self_update(self):
        src = """
            CREATE TRIGGER trg_Orders_AU ON dbo.Orders AFTER UPDATE AS
            BEGIN
                UPDATE dbo.Orders SET ModifiedAt = GETDATE() WHERE OrderId IN (SELECT OrderId FROM inserted);
            END
        """
        obj = _trigger(src)
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert "recursion" in findings[0].issue.lower()

    def test_no_finding_on_different_table(self):
        src = """
            CREATE TRIGGER trg_Orders_AI ON dbo.Orders AFTER INSERT AS
            BEGIN
                INSERT INTO dbo.AuditLog (Event) VALUES ('inserted');
            END
        """
        obj = _trigger(src)
        assert self.rule.analyse(obj) == []
