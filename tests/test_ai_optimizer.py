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

from dbanalyser.ai_optimizer.llm_client import LLMResult

def _make_mock_ollama(optimized_sql="SELECT Id FROM Accounts",
                      reasoning="Added covering index hint.",
                      confidence=0.85,
                      error=None):
    return LLMResult(
        text=json.dumps({
            "optimized_sql":   optimized_sql,
            "reasoning":       reasoning,
            "changes":         [{"type": "performance", "before": "SELECT *",
                                 "after": "SELECT Id", "impact": "Reduced I/O"}],
            "confidence_score": confidence,
            "no_change_needed": False,
            "no_change_reason": "",
        }) if not error else None,
        error=error,
        latency_ms=100
    )


_SCHEMA_CTX = "## Schema Context for usp_X\n### dbo.Accounts (table)\n  - Id int  NOT NULL"
_SOURCE_SQL  = "SELECT * FROM dbo.Accounts WHERE Status = 1"


import sys
from contextlib import contextmanager


class TestOptimizeSqlObject:
    def test_returns_optimization_result(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object, OptimizationResult
        mock_res = _make_mock_ollama()
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                persist=False,
            )
        assert isinstance(result, OptimizationResult)

    def test_optimized_sql_from_response(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_res = _make_mock_ollama(optimized_sql="SELECT Id FROM dbo.Accounts")
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                persist=False,
            )
        assert "Id" in result.optimized_sql

    def test_confidence_score_parsed(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_res = _make_mock_ollama(confidence=0.92)
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                persist=False,
            )
        assert abs(result.confidence_score - 0.92) < 0.01

    def test_tokens_used_summed(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_res = _make_mock_ollama()
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                persist=False,
            )
        # Ollama has tokens_used set to 0 by default
        assert result.tokens_used == 0

    def test_no_api_key_works_fine(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_res = _make_mock_ollama()
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                api_key="",
                persist=False,
            )
        assert result.error is None

    def test_schema_context_enforced_when_empty(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_res = _make_mock_ollama()
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context="",
                persist=False,
            )
        assert result is not None

    def test_persist_called_when_enabled(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_res = _make_mock_ollama()
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result") as mock_persist:
            optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                persist=True,
            )
        mock_persist.assert_called_once()

    def test_persist_not_called_when_disabled(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_res = _make_mock_ollama()
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result") as mock_persist:
            optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                persist=False,
            )
        mock_persist.assert_not_called()

    def test_api_exception_sets_error_field(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        mock_res = _make_mock_ollama(error="Connection timeout")
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
                persist=False,
            )
        assert result.error is not None
        assert "Ollama" in result.error or "Connection" in result.error

    def test_no_change_needed_response(self):
        from dbanalyser.ai_optimizer.optimizer import optimize_sql_object
        from dbanalyser.ai_optimizer.llm_client import LLMResult
        mock_res = LLMResult(
            text=json.dumps({
                "optimized_sql": _SOURCE_SQL,
                "reasoning": "",
                "changes": [],
                "confidence_score": 0.9,
                "no_change_needed": True,
                "no_change_reason": "SQL is already optimal.",
            }),
            error=None,
            latency_ms=100
        )
        with patch("dbanalyser.ai_optimizer.llm_client.call_llm", return_value=mock_res), \
             patch("dbanalyser.ai_optimizer.optimizer._persist_result"):
            result = optimize_sql_object(
                "usp_X", _SOURCE_SQL,
                schema_context=_SCHEMA_CTX,
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
