"""
Tests for dbanalyser.ai_optimizer
======================================
All Anthropic API calls are mocked — no network access required.
"""
import json
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# context_builder
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildOptimizationContext:
    _SQL = "SELECT * FROM Accounts WHERE Status = 1"
    _FINDINGS = [{"rule_id": "PERF001", "severity": "High", "issue": "SELECT *"}]

    def _good_schema(self):
        return "## Schema Context for usp_Test\n### dbo.Accounts (table)\n  - Id int  NOT NULL"

    def test_returns_dict_with_required_keys(self):
        from dbanalyser.ai_optimizer.context_builder import build_optimization_context
        with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
                   return_value=self._good_schema()):
            ctx = build_optimization_context("usp_Test", self._SQL,
                                              findings=self._findings())
        for key in ("schema_context", "findings", "execution_plan",
                    "context_quality", "warnings"):
            assert key in ctx

    def _findings(self):
        return [{"rule_id": "PERF001", "severity": "High", "issue": "SELECT *"}]

    def test_good_quality_all_present(self):
        from dbanalyser.ai_optimizer.context_builder import build_optimization_context
        with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
                   return_value=self._good_schema()):
            ctx = build_optimization_context(
                "usp_Test", self._SQL,
                findings=self._findings(),
                execution_plan="Cost=1.234",
            )
        assert ctx["context_quality"] == "good"

    def test_partial_quality_schema_only(self):
        from dbanalyser.ai_optimizer.context_builder import build_optimization_context
        with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
                   return_value=self._good_schema()):
            ctx = build_optimization_context("usp_Test", self._SQL)
        assert ctx["context_quality"] in ("partial", "good")

    def test_none_quality_no_schema_no_findings(self):
        from dbanalyser.ai_optimizer.context_builder import build_optimization_context
        with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
                   return_value="## Schema Context\n*not available*"):
            ctx = build_optimization_context("usp_Test", self._SQL)
        assert ctx["context_quality"] == "none"

    def test_warnings_when_no_plan(self):
        from dbanalyser.ai_optimizer.context_builder import build_optimization_context
        with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
                   return_value=self._good_schema()):
            ctx = build_optimization_context("usp_Test", self._SQL)
        warn_text = " ".join(ctx["warnings"]).lower()
        assert "execution plan" in warn_text

    def test_warnings_when_no_findings(self):
        from dbanalyser.ai_optimizer.context_builder import build_optimization_context
        with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
                   return_value=self._good_schema()):
            ctx = build_optimization_context("usp_Test", self._SQL, findings=[])
        warn_text = " ".join(ctx["warnings"]).lower()
        assert "finding" in warn_text

    def test_schema_retrieval_error_captured_in_warnings(self):
        from dbanalyser.ai_optimizer.context_builder import build_optimization_context
        with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
                   side_effect=RuntimeError("DB connection refused")):
            ctx = build_optimization_context("usp_Test", self._SQL)
        warn_text = " ".join(ctx["warnings"]).lower()
        assert "schema" in warn_text or "error" in warn_text

    def test_findings_passed_through(self):
        from dbanalyser.ai_optimizer.context_builder import build_optimization_context
        findings = [
            {"rule_id": "SEC001", "severity": "Critical", "issue": "SA login"},
            {"rule_id": "PERF002", "severity": "High", "issue": "Missing index"},
        ]
        with patch("dbanalyser.schema_intel.searcher.build_schema_context_for_object",
                   return_value=self._good_schema()):
            ctx = build_optimization_context("usp_Test", self._SQL, findings=findings)
        assert len(ctx["findings"]) == 2


# ─────────────────────────────────────────────────────────────────────────────
# optimizer — optimize_sql_object
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_anthropic(optimized_sql="SELECT Id FROM Accounts",
                          reasoning="Added covering index hint.",
                          confidence=0.85,
                          input_tokens=500,
                          output_tokens=300):
    """Return a mock anthropic.Anthropic() client that returns structured JSON."""
    mock_client     = MagicMock()
    mock_message    = MagicMock()
    mock_usage      = MagicMock()
    mock_usage.input_tokens  = input_tokens
    mock_usage.output_tokens = output_tokens
    mock_message.usage   = mock_usage
    mock_message.content = [MagicMock(text=json.dumps({
        "optimized_sql":   optimized_sql,
        "reasoning":       reasoning,
        "changes":         [{"type": "performance", "before": "SELECT *",
                             "after": "SELECT Id", "impact": "Reduced I/O"}],
        "confidence_score": confidence,
        "no_change_needed": False,
        "no_change_reason": "",
    }))]
    mock_client.messages.create.return_value = mock_message
    return mock_client


_SCHEMA_CTX = "## Schema Context for usp_X\n### dbo.Accounts (table)\n  - Id int  NOT NULL"
_SOURCE_SQL  = "SELECT * FROM dbo.Accounts WHERE Status = 1"


import sys
from contextlib import contextmanager


@contextmanager
def _mock_anthropic(mock_client):
    """Context manager: inject mock anthropic module into sys.modules."""
    mock_module = MagicMock()
    mock_module.Anthropic.return_value = mock_client
    old = sys.modules.get("anthropic")
    sys.modules["anthropic"] = mock_module
    try:
        yield mock_module
    finally:
        if old is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = old


class TestOptimizeSqlObject:
    def test_returns_optimization_result(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object, OptimizationResult
        mock_client = _make_mock_anthropic()
        with _mock_anthropic(mock_client), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="sk-test",
                persist=False,
            )
        assert isinstance(result, OptimizationResult)

    def test_optimized_sql_from_response(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_client = _make_mock_anthropic(optimized_sql="SELECT Id FROM dbo.Accounts")
        with _mock_anthropic(mock_client), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="sk-test",
                persist=False,
            )
        assert "Id" in result.optimized_sql

    def test_confidence_score_parsed(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_client = _make_mock_anthropic(confidence=0.92)
        with _mock_anthropic(mock_client), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="sk-test",
                persist=False,
            )
        assert abs(result.confidence_score - 0.92) < 0.01

    def test_tokens_used_summed(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_client = _make_mock_anthropic(input_tokens=400, output_tokens=200)
        with _mock_anthropic(mock_client), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="sk-test",
                persist=False,
            )
        assert result.tokens_used == 600

    def test_no_api_key_returns_error(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        import os
        env_backup = {k: v for k, v in os.environ.items()
                      if k in ("ANTHROPIC_API_KEY", "DBANALYSER_AI_OPTIMIZER_API_KEY")}
        for k in list(env_backup):
            del os.environ[k]
        try:
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="",
                persist=False,
            )
        finally:
            os.environ.update(env_backup)
        assert result.error is not None
        assert "api key" in result.error.lower()

    def test_missing_anthropic_package_returns_error(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        # Remove anthropic from sys.modules to simulate it not being installed
        old = sys.modules.pop("anthropic", None)
        # Prevent re-import by inserting None
        sys.modules["anthropic"] = None  # type: ignore
        try:
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="sk-test",
                persist=False,
            )
        finally:
            if old is None:
                sys.modules.pop("anthropic", None)
            else:
                sys.modules["anthropic"] = old
        assert result.error is not None

    def test_schema_context_enforced_when_empty(self):
        """When schema_context is empty the optimizer should log a warning but continue."""
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_client = _make_mock_anthropic()
        with _mock_anthropic(mock_client), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context="",
                api_key="sk-test",
                persist=False,
            )
        assert result is not None

    def test_persist_called_when_enabled(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_client = _make_mock_anthropic()
        with _mock_anthropic(mock_client), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result") as mock_persist:
            optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="sk-test",
                persist=True,
            )
        mock_persist.assert_called_once()

    def test_persist_not_called_when_disabled(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_client = _make_mock_anthropic()
        with _mock_anthropic(mock_client), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result") as mock_persist:
            optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="sk-test",
                persist=False,
            )
        mock_persist.assert_not_called()

    def test_api_exception_sets_error_field(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("Rate limit exceeded")
        with _mock_anthropic(mock_client), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="sk-test",
                persist=False,
            )
        assert result.error is not None
        assert "Rate limit" in result.error

    def test_no_change_needed_response(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_client     = MagicMock()
        mock_message    = MagicMock()
        mock_usage      = MagicMock()
        mock_usage.input_tokens  = 100
        mock_usage.output_tokens = 50
        mock_message.usage   = mock_usage
        mock_message.content = [MagicMock(text=json.dumps({
            "optimized_sql": _SOURCE_SQL,
            "reasoning": "",
            "changes": [],
            "confidence_score": 0.9,
            "no_change_needed": True,
            "no_change_reason": "SQL is already optimal.",
        }))]
        mock_client.messages.create.return_value = mock_message
        with _mock_anthropic(mock_client), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="sk-test",
                persist=False,
            )
        assert "No optimization needed" in result.reasoning or result.error is None


# ─────────────────────────────────────────────────────────────────────────────
# _format_reasoning
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatReasoning:
    def test_no_change_needed_message(self):
        from dbanalyser.ai_optimizer.optimizer import _format_reasoning
        data = {"no_change_needed": True, "no_change_reason": "Already optimal."}
        text = _format_reasoning(data)
        assert "No optimization needed" in text

    def test_includes_reasoning_text(self):
        from dbanalyser.ai_optimizer.optimizer import _format_reasoning
        data = {
            "no_change_needed": False,
            "reasoning": "Replaced SELECT * with specific columns.",
            "changes": [],
        }
        text = _format_reasoning(data)
        assert "Replaced SELECT" in text

    def test_includes_changes(self):
        from dbanalyser.ai_optimizer.optimizer import _format_reasoning
        data = {
            "no_change_needed": False,
            "reasoning": "Optimized.",
            "changes": [
                {"type": "performance", "before": "SELECT *",
                 "after": "SELECT Id", "impact": "Reduced I/O"}
            ],
        }
        text = _format_reasoning(data)
        assert "Change 1" in text
        assert "performance" in text
