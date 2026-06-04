"""
Unit tests — compliance rule packs (SOX, GDPR, RBI).

Run with:
    cd D:\\LTFS\\ltfs-analyzer
    python -m pytest tests/test_compliance.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from dbanalyser.engine.rules.base import SQLObject
from dbanalyser.engine.rules.compliance.sox import (
    SoxMissingAuditColumnsRule,
    SoxDirectDmlWithoutAuditRule,
    SoxXpCmdshellInFinancialRule,
    SoxGrantOnFinancialTableRule,
    SoxNoErrorHandlingInTransactionRule,
)
from dbanalyser.engine.rules.compliance.gdpr import (
    GdprPiiColumnInSelectStarRule,
    GdprPiiInPrintOrRaiserrorRule,
    GdprUnmaskedPiiReturnRule,
    GdprHardcodedPersonalDataRule,
    GdprMissingRetentionHintRule,
)
from dbanalyser.engine.rules.compliance.rbi import (
    RbiUnencryptedFinancialDataRule,
    RbiMissingTransactionAuditRule,
    RbiNoErrorHandlingInFinancialSpRule,
    RbiHardcodedConnectionStringRule,
)
from dbanalyser.engine.rules.compliance import get_compliance_rules, COMPLIANCE_PACKS


# ── helpers ───────────────────────────────────────────────────────────────────

def _sp(source: str, name: str = "usp_Test") -> SQLObject:
    return SQLObject(name=name, obj_type="Stored Procedure",
                     schema="dbo", source=source)


def _table(source: str, name: str = "Accounts") -> SQLObject:
    return SQLObject(name=name, obj_type="Table",
                     schema="dbo", source=source)


def _view(source: str, name: str = "vw_AccountSummary") -> SQLObject:
    return SQLObject(name=name, obj_type="View",
                     schema="dbo", source=source)


# ═════════════════════════════════════════════════════════════════════════════
# SOX rules
# ═════════════════════════════════════════════════════════════════════════════

class TestSoxMissingAuditColumnsRule:
    rule = SoxMissingAuditColumnsRule()

    def test_detects_financial_table_without_audit_cols(self):
        obj = _table(
            "CREATE TABLE dbo.Ledger (Id INT, Amount DECIMAL(18,2))",
            name="Ledger",
        )
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert "audit" in findings[0].issue.lower()

    def test_no_finding_with_created_by(self):
        obj = _table(
            "CREATE TABLE dbo.Ledger (Id INT, Amount DECIMAL, CreatedBy NVARCHAR(100))",
            name="Ledger",
        )
        assert self.rule.analyse(obj) == []

    def test_skips_non_financial_table(self):
        obj = _table(
            "CREATE TABLE dbo.SystemLogs (Id INT, Message NVARCHAR(500))",
            name="SystemLogs",
        )
        assert self.rule.analyse(obj) == []


class TestSoxDirectDmlWithoutAuditRule:
    rule = SoxDirectDmlWithoutAuditRule()

    def test_detects_insert_without_audit_log(self):
        src = """
            CREATE PROCEDURE dbo.usp_PostTransaction AS
            BEGIN
                INSERT INTO dbo.Ledger (Amount) VALUES (@Amount);
            END
        """
        obj = _sp(src, name="usp_PostTransaction")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert "audit" in findings[0].recommendation.lower()

    def test_no_finding_with_audit_insert(self):
        src = """
            CREATE PROCEDURE dbo.usp_PostTransaction AS
            BEGIN
                INSERT INTO dbo.Ledger (Amount) VALUES (@Amount);
                INSERT INTO dbo.LedgerAudit (Action, Amount) VALUES ('INSERT', @Amount);
            END
        """
        obj = _sp(src, name="usp_PostTransaction")
        assert self.rule.analyse(obj) == []


class TestSoxXpCmdshellInFinancialRule:
    rule = SoxXpCmdshellInFinancialRule()

    def test_detects_xp_cmdshell_in_financial_sp(self):
        src = "CREATE PROCEDURE dbo.usp_ExportLedger AS EXEC xp_cmdshell 'bcp ...'"
        obj = _sp(src, name="usp_ExportLedger")
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert findings[0].severity == "Critical"


class TestSoxGrantOnFinancialTableRule:
    rule = SoxGrantOnFinancialTableRule()

    def test_detects_grant_on_financial_table(self):
        src = "GRANT SELECT ON dbo.AccountLedger TO [AppUser]"
        obj = _sp(src, name="usp_Setup")
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert "AccountLedger" in findings[0].issue

    def test_no_finding_on_non_financial_table(self):
        src = "GRANT SELECT ON dbo.UISettings TO [AppUser]"
        obj = _sp(src, name="usp_Setup")
        assert self.rule.analyse(obj) == []


class TestSoxNoErrorHandlingInTransactionRule:
    rule = SoxNoErrorHandlingInTransactionRule()

    def test_detects_missing_try_catch(self):
        src = """
            CREATE PROCEDURE dbo.usp_PostPayment AS
            BEGIN
                BEGIN TRANSACTION;
                INSERT INTO dbo.Payment (Amount) VALUES (@Amt);
                COMMIT;
            END
        """
        obj = _sp(src, name="usp_PostPayment")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1

    def test_no_finding_with_try_catch(self):
        src = """
            CREATE PROCEDURE dbo.usp_PostPayment AS
            BEGIN
                BEGIN TRY
                    BEGIN TRANSACTION;
                    INSERT INTO dbo.Payment (Amount) VALUES (@Amt);
                    COMMIT;
                END TRY
                BEGIN CATCH
                    ROLLBACK;
                END CATCH
            END
        """
        obj = _sp(src, name="usp_PostPayment")
        assert self.rule.analyse(obj) == []


# ═════════════════════════════════════════════════════════════════════════════
# GDPR rules
# ═════════════════════════════════════════════════════════════════════════════

class TestGdprPiiColumnInSelectStarRule:
    rule = GdprPiiColumnInSelectStarRule()

    def test_detects_select_star_on_pii_object(self):
        src = "SELECT * FROM dbo.CustomerProfiles WHERE email IS NOT NULL"
        obj = _sp(src)
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert "SELECT *" in findings[0].issue

    def test_no_finding_when_no_pii_reference(self):
        obj = _sp("SELECT * FROM dbo.Products")
        assert self.rule.analyse(obj) == []

    def test_no_finding_with_explicit_columns(self):
        src = "SELECT CustomerId, email FROM dbo.Customers"
        obj = _sp(src)
        assert self.rule.analyse(obj) == []


class TestGdprPiiInPrintOrRaiserrorRule:
    rule = GdprPiiInPrintOrRaiserrorRule()

    def test_detects_print_with_pii_column(self):
        src = "PRINT 'Email: ' + email"
        obj = _sp(src)
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert "PII" in findings[0].issue

    def test_no_finding_without_pii(self):
        src = "PRINT 'Processing complete'"
        obj = _sp(src)
        assert self.rule.analyse(obj) == []


class TestGdprUnmaskedPiiReturnRule:
    rule = GdprUnmaskedPiiReturnRule()

    def test_detects_view_returning_email_without_masking(self):
        src = "CREATE VIEW dbo.vw_CustomerData AS SELECT email, phone FROM dbo.Customers"
        obj = _view(src, name="vw_CustomerData")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert "mask" in findings[0].recommendation.lower()

    def test_no_finding_with_masking_function(self):
        src = "CREATE VIEW dbo.vw_CustomerData AS SELECT HASHBYTES('SHA2_256', email) AS email_hash FROM dbo.Customers"
        obj = _view(src, name="vw_CustomerData")
        assert self.rule.analyse(obj) == []


class TestGdprHardcodedPersonalDataRule:
    rule = GdprHardcodedPersonalDataRule()

    def test_detects_hardcoded_email(self):
        src = "INSERT INTO dbo.T (Email) VALUES ('john.doe@example.com')"
        obj = _sp(src)
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert "email" in findings[0].issue.lower()

    def test_no_finding_on_placeholder(self):
        obj = _sp("SELECT Id FROM dbo.T WHERE Status = 'Active'")
        assert self.rule.analyse(obj) == []


class TestGdprMissingRetentionHintRule:
    rule = GdprMissingRetentionHintRule()

    def test_detects_pii_table_without_retention(self):
        src = "CREATE TABLE dbo.CustomerContacts (Id INT, email NVARCHAR(200), phone NVARCHAR(50))"
        obj = _table(src, name="CustomerContacts")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert "retention" in findings[0].recommendation.lower()

    def test_no_finding_with_retention_comment(self):
        src = """
            -- GDPR: retention 6 years, purge via sp_PurgeContacts
            CREATE TABLE dbo.CustomerContacts (Id INT, email NVARCHAR(200))
        """
        obj = _table(src, name="CustomerContacts")
        assert self.rule.analyse(obj) == []

    def test_skips_non_pii_table(self):
        src = "CREATE TABLE dbo.Products (Id INT, Name NVARCHAR(100))"
        obj = _table(src, name="Products")
        assert self.rule.analyse(obj) == []


# ═════════════════════════════════════════════════════════════════════════════
# RBI rules
# ═════════════════════════════════════════════════════════════════════════════

class TestRbiUnencryptedFinancialDataRule:
    rule = RbiUnencryptedFinancialDataRule()

    def test_detects_unencrypted_account_no(self):
        src = "CREATE TABLE dbo.BankAccounts (Id INT, account_no NVARCHAR(20), balance DECIMAL)"
        obj = _table(src, name="BankAccounts")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert findings[0].severity == "Critical"

    def test_no_finding_with_encryption(self):
        src = """
            CREATE TABLE dbo.BankAccounts (
                Id INT,
                account_no VARBINARY(256),  -- ENCRYPTBYKEY applied at app layer
                balance DECIMAL
            )
        """
        obj = _table(src, name="BankAccounts")
        # Contains ENCRYPTBYKEY hint — no finding
        src2 = src + "\n-- ENCRYPTBYKEY(KEY_GUID('DataKey'), account_no)"
        obj2 = _table(src2, name="BankAccounts")
        assert self.rule.analyse(obj2) == []

    def test_skips_non_financial_table(self):
        src = "CREATE TABLE dbo.AppConfig (Key NVARCHAR(100), Value NVARCHAR(200))"
        obj = _table(src, name="AppConfig")
        assert self.rule.analyse(obj) == []


class TestRbiMissingTransactionAuditRule:
    rule = RbiMissingTransactionAuditRule()

    def test_detects_sp_without_audit_log(self):
        src = """
            CREATE PROCEDURE dbo.usp_TransferFunds AS
            BEGIN
                UPDATE dbo.Account SET Balance = Balance - @Amt WHERE AccountId = @From;
                UPDATE dbo.Account SET Balance = Balance + @Amt WHERE AccountId = @To;
            END
        """
        obj = _sp(src, name="usp_TransferFunds")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert findings[0].severity == "Critical"

    def test_no_finding_with_audit_log(self):
        src = """
            CREATE PROCEDURE dbo.usp_TransferFunds AS
            BEGIN
                UPDATE dbo.Account SET Balance = Balance - @Amt WHERE AccountId = @From;
                INSERT INTO dbo.TransactionAudit (Action, Amount) VALUES ('DEBIT', @Amt);
            END
        """
        obj = _sp(src, name="usp_TransferFunds")
        assert self.rule.analyse(obj) == []


class TestRbiNoErrorHandlingInFinancialSpRule:
    rule = RbiNoErrorHandlingInFinancialSpRule()

    def test_detects_missing_rollback(self):
        src = """
            CREATE PROCEDURE dbo.usp_PostEMI AS
            BEGIN
                BEGIN TRY
                    BEGIN TRANSACTION;
                    INSERT INTO dbo.LoanRepayment (Amount) VALUES (@Amt);
                    COMMIT;
                END TRY
                BEGIN CATCH
                    THROW;
                END CATCH
            END
        """
        obj = _sp(src, name="usp_PostEMI")
        findings = self.rule.analyse(obj)
        assert len(findings) == 1
        assert "ROLLBACK" in findings[0].recommendation

    def test_no_finding_with_full_error_handling(self):
        src = """
            CREATE PROCEDURE dbo.usp_PostEMI AS
            BEGIN
                BEGIN TRY
                    BEGIN TRANSACTION;
                    INSERT INTO dbo.LoanRepayment (Amount) VALUES (@Amt);
                    COMMIT;
                END TRY
                BEGIN CATCH
                    ROLLBACK TRANSACTION;
                    THROW;
                END CATCH
            END
        """
        obj = _sp(src, name="usp_PostEMI")
        assert self.rule.analyse(obj) == []


class TestRbiHardcodedConnectionStringRule:
    rule = RbiHardcodedConnectionStringRule()

    def test_detects_hardcoded_connection_string(self):
        src = "SET @conn = 'Data Source=prod-sql;Initial Catalog=CoreBanking;Password=Secret123'"
        obj = _sp(src, name="usp_ExportRemittance")
        findings = self.rule.analyse(obj)
        assert len(findings) >= 1
        assert findings[0].severity == "High"

    def test_no_finding_on_clean_sp(self):
        src = "SELECT amount FROM dbo.Remittance WHERE txn_id = @Id"
        obj = _sp(src, name="usp_GetRemittance")
        assert self.rule.analyse(obj) == []


# ═════════════════════════════════════════════════════════════════════════════
# Compliance pack registry
# ═════════════════════════════════════════════════════════════════════════════

class TestCompliancePackRegistry:

    def test_all_packs_registered(self):
        assert set(COMPLIANCE_PACKS) == {"sox", "gdpr", "rbi"}

    def test_get_sox_rules(self):
        rules = get_compliance_rules(["sox"])
        rule_ids = [r.rule_id for r in rules]
        assert "SOX001" in rule_ids
        assert "SOX006" in rule_ids
        # Should NOT contain GDPR or RBI rules
        assert all(r.startswith("SOX") for r in rule_ids)

    def test_get_multiple_packs(self):
        rules = get_compliance_rules(["gdpr", "rbi"])
        rule_ids = [r.rule_id for r in rules]
        assert any(r.startswith("GDPR") for r in rule_ids)
        assert any(r.startswith("RBI") for r in rule_ids)
        assert not any(r.startswith("SOX") for r in rule_ids)

    def test_empty_packs_returns_empty(self):
        assert get_compliance_rules([]) == []

    def test_unknown_pack_skipped_gracefully(self):
        rules = get_compliance_rules(["sox", "unknown_pack"])
        # Should still return SOX rules, unknown silently ignored
        assert len(rules) > 0
        assert all(r.rule_id.startswith("SOX") for r in rules)


# ═════════════════════════════════════════════════════════════════════════════
# build_rule_set integration — compliance packs extend ALL_RULES
# ═════════════════════════════════════════════════════════════════════════════

class TestBuildRuleSetIntegration:

    def test_no_compliance_without_config(self):
        from dbanalyser.engine.rules import ALL_RULES, build_rule_set
        rules = build_rule_set(cfg=None)
        assert rules == list(ALL_RULES)

    def test_compliance_rules_added_when_enabled(self):
        from dbanalyser.engine.rules import ALL_RULES, build_rule_set
        from dbanalyser.config import Settings, ComplianceConfig

        cfg = Settings(compliance=ComplianceConfig(enabled_packs=["sox"]))
        rules = build_rule_set(cfg=cfg)
        rule_ids = [r.rule_id for r in rules]
        # Base rules still present
        assert "SEC001" in rule_ids
        # SOX rules added
        assert "SOX001" in rule_ids
        assert len(rules) > len(list(ALL_RULES))

    def test_empty_packs_returns_base_rules_only(self):
        from dbanalyser.engine.rules import ALL_RULES, build_rule_set
        from dbanalyser.config import Settings, ComplianceConfig

        cfg = Settings(compliance=ComplianceConfig(enabled_packs=[]))
        rules = build_rule_set(cfg=cfg)
        assert len(rules) == len(list(ALL_RULES))
