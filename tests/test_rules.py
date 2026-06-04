"""
Unit tests for the DBAnalyser rule engine.

Run with:
    cd D:\\LTFS\\ltfs-analyzer
    python -m pytest tests/ -v
"""

import sys
import os
from pathlib import Path

# Allow imports from the package root
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from dbanalyser.engine.rules.base import SQLObject, RuleFinding
from dbanalyser.engine.rules.performance      import (
    SelectStarRule, MissingNoCountRule, CursorUsageRule,
    NolockHintRule, NonSargableWhereRule,
)
from dbanalyser.engine.rules.security         import (
    DynamicSqlInjectionRule, HardcodedCredentialRule,
    XpCmdshellRule,
)
from dbanalyser.engine.rules.reliability      import (
    MissingTryCatchRule, TransactionWithoutRollbackRule,
)
from dbanalyser.engine.rules.best_practices   import (
    MissingAnsiNullsRule, MissingQuotedIdentifierRule,
    SpPrefixOnUserSpRule, MissingSchemaQualifierRule,
)
from dbanalyser.engine.rules.data_safety      import (
    ImplicitNullComparisonRule, NullInNotInSubqueryRule,
    DataTruncationRiskRule,
)
from dbanalyser.engine.rules.maintainability  import LongProcedureRule
from dbanalyser.engine.rules.parameter_sniffing import (
    OptionalParamAntipatternRule,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sp(source: str, name: str = "TestProc") -> SQLObject:
    return SQLObject(name=name, obj_type="Stored Procedure",
                     schema="dbo", source=source)


def _view(source: str, name: str = "TestView") -> SQLObject:
    return SQLObject(name=name, obj_type="View", schema="dbo", source=source)


def _table(source: str, name: str = "TestTable") -> SQLObject:
    return SQLObject(name=name, obj_type="Table", schema="dbo", source=source)


# ── Performance rules ─────────────────────────────────────────────────────────

class TestSelectStarRule:
    rule = SelectStarRule()

    def test_detects_select_star(self):
        obj = _sp("SELECT * FROM dbo.Orders")
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert findings[0].severity == "High"

    def test_no_false_positive_explicit_cols(self):
        obj = _sp("SELECT OrderId, OrderDate FROM dbo.Orders")
        assert self.rule.analyse(obj) == []


class TestMissingNoCountRule:
    rule = MissingNoCountRule()

    def test_detects_missing_nocount(self):
        obj = _sp("CREATE PROCEDURE dbo.Test AS BEGIN SELECT 1 END")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert "NOCOUNT" in findings[0].issue

    def test_passes_with_nocount(self):
        obj = _sp("CREATE PROCEDURE dbo.Test AS BEGIN SET NOCOUNT ON; SELECT 1 END")
        assert self.rule.analyse(obj) == []

    def test_skips_non_sp(self):
        obj = _view("SELECT 1")
        assert self.rule.analyse(obj) == []


class TestCursorUsageRule:
    rule = CursorUsageRule()

    def test_detects_cursor(self):
        obj = _sp("DECLARE myCur CURSOR FOR SELECT Id FROM dbo.T")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert findings[0].severity == "High"

    def test_no_cursor(self):
        obj = _sp("SELECT Id FROM dbo.T")
        assert self.rule.analyse(obj) == []


class TestNolockHintRule:
    rule = NolockHintRule()

    def test_detects_nolock(self):
        obj = _sp("SELECT * FROM dbo.Orders WITH (NOLOCK)")
        assert len(self.rule.analyse(obj)) == 1

    def test_no_nolock(self):
        obj = _sp("SELECT * FROM dbo.Orders")
        assert self.rule.analyse(obj) == []


class TestNonSargableWhereRule:
    rule = NonSargableWhereRule()

    def test_detects_leading_wildcard(self):
        obj = _sp("SELECT Id FROM dbo.T WHERE Name LIKE '%Smith'")
        assert len(self.rule.analyse(obj)) >= 1

    def test_trailing_wildcard_ok(self):
        obj = _sp("SELECT Id FROM dbo.T WHERE Name LIKE 'Smith%'")
        assert self.rule.analyse(obj) == []


# ── Security rules ────────────────────────────────────────────────────────────

class TestDynamicSqlInjectionRule:
    rule = DynamicSqlInjectionRule()

    def test_detects_exec_variable(self):
        obj = _sp("EXEC(@sql)")
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert findings[0].severity == "Critical"

    def test_detects_string_concat(self):
        obj = _sp("EXECUTE('SELECT ' + @col)")
        assert len(self.rule.analyse(obj)) >= 1

    def test_sp_executesql_with_params_ok(self):
        obj = _sp("EXEC sp_executesql @stmt, N'@id INT', @id=@CustomerId")
        assert self.rule.analyse(obj) == []


class TestHardcodedCredentialRule:
    rule = HardcodedCredentialRule()

    def test_detects_password_literal(self):
        obj = _sp("SET @password = 'MySecret123'")
        assert len(self.rule.analyse(obj)) >= 1

    def test_no_false_positive(self):
        obj = _sp("SELECT CustomerName FROM dbo.Customers")
        assert self.rule.analyse(obj) == []


class TestXpCmdshellRule:
    rule = XpCmdshellRule()

    def test_detects_xp_cmdshell(self):
        obj = _sp("EXEC xp_cmdshell 'dir C:\\'")
        assert len(self.rule.analyse(obj)) >= 1
        assert self.rule.analyse(obj)[0].severity == "Critical"


# ── Reliability rules ─────────────────────────────────────────────────────────

class TestMissingTryCatchRule:
    rule = MissingTryCatchRule()

    def test_detects_missing_try_catch(self):
        obj = _sp("CREATE PROCEDURE dbo.Test AS INSERT INTO dbo.T VALUES(1)")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert findings[0].severity == "High"

    def test_passes_with_try_catch(self):
        obj = _sp("""
            CREATE PROCEDURE dbo.Test AS
            BEGIN TRY
                INSERT INTO dbo.T VALUES(1)
            END TRY
            BEGIN CATCH
                THROW;
            END CATCH
        """)
        assert self.rule.analyse(obj) == []

    def test_skips_view(self):
        obj = _view("SELECT 1")
        assert self.rule.analyse(obj) == []


class TestTransactionWithoutRollbackRule:
    rule = TransactionWithoutRollbackRule()

    def test_detects_begin_tran_without_catch(self):
        obj = _sp("BEGIN TRANSACTION; INSERT INTO dbo.T VALUES(1); COMMIT TRANSACTION;")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1

    def test_detects_catch_without_rollback(self):
        obj = _sp("""
            BEGIN TRANSACTION;
            BEGIN TRY
                INSERT INTO dbo.T VALUES(1);
                COMMIT TRANSACTION;
            END TRY
            BEGIN CATCH
                THROW;
            END CATCH
        """)
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert "ROLLBACK" in findings[0].recommendation


# ── Best practices ────────────────────────────────────────────────────────────

class TestMissingAnsiNullsRule:
    rule = MissingAnsiNullsRule()

    def test_detects_missing(self):
        obj = _sp("CREATE PROCEDURE dbo.Test AS SELECT 1")
        assert len(self.rule.analyse(obj)) == 1

    def test_passes_with_setting(self):
        obj = _sp("SET ANSI_NULLS ON\nGO\nCREATE PROCEDURE dbo.Test AS SELECT 1")
        assert self.rule.analyse(obj) == []


class TestSpPrefixOnUserSpRule:
    rule = SpPrefixOnUserSpRule()

    def test_detects_sp_prefix(self):
        obj = _sp("", name="sp_GetOrders")
        assert len(self.rule.analyse(obj)) == 1

    def test_usp_prefix_ok(self):
        obj = _sp("", name="usp_GetOrders")
        assert self.rule.analyse(obj) == []


class TestMissingSchemaQualifierRule:
    rule = MissingSchemaQualifierRule()

    def test_detects_unqualified_from(self):
        obj = _sp("SELECT * FROM Orders")
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert "schema" in findings[0].issue.lower()

    def test_qualified_no_finding(self):
        obj = _sp("SELECT * FROM dbo.Orders")
        assert self.rule.analyse(obj) == []


# ── Data safety rules ─────────────────────────────────────────────────────────

class TestImplicitNullComparisonRule:
    rule = ImplicitNullComparisonRule()

    def test_detects_equals_null(self):
        obj = _sp("SELECT * FROM dbo.T WHERE Col = NULL")
        assert len(self.rule.analyse(obj)) >= 1

    def test_is_null_ok(self):
        obj = _sp("SELECT * FROM dbo.T WHERE Col IS NULL")
        assert self.rule.analyse(obj) == []


class TestNullInNotInSubqueryRule:
    rule = NullInNotInSubqueryRule()

    def test_detects_not_in_select(self):
        obj = _sp("SELECT * FROM dbo.T WHERE Id NOT IN (SELECT Id FROM dbo.Other)")
        assert len(self.rule.analyse(obj)) >= 1

    def test_not_in_literal_ok(self):
        obj = _sp("SELECT * FROM dbo.T WHERE Id NOT IN (1, 2, 3)")
        assert self.rule.analyse(obj) == []


class TestDataTruncationRiskRule:
    rule = DataTruncationRiskRule()

    def test_detects_small_varchar(self):
        obj = _sp("SELECT CONVERT(VARCHAR(5), LongDescription) FROM dbo.T")
        assert len(self.rule.analyse(obj)) >= 1

    def test_large_varchar_ok(self):
        obj = _sp("SELECT CONVERT(VARCHAR(200), Description) FROM dbo.T")
        assert self.rule.analyse(obj) == []


# ── Maintainability ───────────────────────────────────────────────────────────

class TestLongProcedureRule:
    rule = LongProcedureRule()

    def test_detects_long_proc(self):
        long_src = "\n".join(["SELECT 1"] * 600)
        obj = SQLObject(name="BigProc", obj_type="Stored Procedure",
                        schema="dbo", source=long_src)
        assert len(self.rule.analyse(obj)) == 1

    def test_short_proc_ok(self):
        obj = _sp("SELECT 1 FROM dbo.T")
        assert self.rule.analyse(obj) == []


# ── Parameter sniffing ────────────────────────────────────────────────────────

class TestOptionalParamAntipatternRule:
    rule = OptionalParamAntipatternRule()

    def test_detects_or_null_pattern(self):
        src = """
            CREATE PROCEDURE dbo.Search @Status INT = NULL AS
            SELECT * FROM dbo.Orders WHERE (@Status IS NULL OR Status = @Status)
        """
        obj = _sp(src)
        assert len(self.rule.analyse(obj)) >= 1

    def test_clean_sp_ok(self):
        obj = _sp("CREATE PROCEDURE dbo.GetById @Id INT AS SELECT * FROM dbo.T WHERE Id = @Id")
        assert self.rule.analyse(obj) == []


# ── Integration: bad_proc fixture ────────────────────────────────────────────

class TestBadProcFixture:
    """Run ALL_RULES against the bad_proc.sql fixture — should find many issues."""

    def test_bad_proc_has_many_findings(self):
        from dbanalyser.engine.rules import ALL_RULES
        fixture = Path(__file__).parent / "fixtures" / "bad_proc.sql"
        source  = fixture.read_text(encoding="utf-8")
        obj = SQLObject(name="sp_GetData", obj_type="Stored Procedure",
                        schema="dbo", source=source)
        findings = []
        for rule in ALL_RULES:
            findings.extend(rule.analyse(obj))
        assert len(findings) >= 5, f"Expected >= 5 findings, got {len(findings)}"

    def test_good_proc_has_few_findings(self):
        from dbanalyser.engine.rules import ALL_RULES
        fixture = Path(__file__).parent / "fixtures" / "good_proc.sql"
        source  = fixture.read_text(encoding="utf-8")
        obj = SQLObject(name="usp_GetCustomerOrders", obj_type="Stored Procedure",
                        schema="dbo", source=source)
        findings = []
        for rule in ALL_RULES:
            findings.extend(rule.analyse(obj))
        # A well-written proc should have no Critical or High findings
        critical_high = [f for f in findings if f.severity in ("Critical", "High")]
        assert len(critical_high) == 0, \
            f"Good proc should have 0 Critical/High, got: {[f.issue for f in critical_high]}"
