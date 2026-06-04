"""
Tests for /ai API routes (optimizer + history).
All DB and Anthropic API calls are mocked.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient

from dbanalyser.api.main import create_app

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    app = create_app(api_key="")
    return TestClient(app)


_OPT_ROW = {
    "id": 1, "run_id": None, "db_registry_id": None,
    "object_name": "usp_GetAccounts", "original_sql": "SELECT * FROM Accounts",
    "optimized_sql": "SELECT Id FROM Accounts",
    "reasoning": "Replaced SELECT *",
    "confidence_score": 0.88, "model_used": "claude-3-5-haiku-20241022",
    "tokens_used": 600, "created_at": None,
}


# ── POST /ai/optimize ─────────────────────────────────────────────────────────

class TestOptimizeEndpoint:
    def _make_result(self, **kwargs):
        """Build a fake OptimizationResult-like object."""
        r = MagicMock()
        r.error             = kwargs.get("error", None)
        r.optimized_sql     = kwargs.get("optimized_sql", "SELECT Id FROM Accounts")
        r.reasoning         = kwargs.get("reasoning", "Replaced SELECT *")
        r.changes           = kwargs.get("changes", [
            {"type": "performance", "before": "SELECT *",
             "after": "SELECT Id", "impact": "Reduced I/O"}
        ])
        r.confidence_score  = kwargs.get("confidence_score", 0.88)
        r.no_change_needed  = kwargs.get("no_change_needed", False)
        r.no_change_reason  = kwargs.get("no_change_reason", "")
        r.tokens_used       = kwargs.get("tokens_used", 600)
        r.model_used        = kwargs.get("model_used", "claude-3-5-haiku-20241022")
        return r

    def test_successful_optimization(self, client):
        fake = self._make_result()
        with patch("dbanalyser.ai_optimizer.optimizer.optimize_sql_object",
                   return_value=fake):
            r = client.post("/ai/optimize", json={
                "object_name": "usp_GetAccounts",
                "sql": "SELECT * FROM Accounts",
                "api_key": "sk-test",
            })
        assert r.status_code == 200
        body = r.json()
        assert body["object_name"] == "usp_GetAccounts"
        assert "Id" in body["optimized_sql"]
        assert abs(body["confidence_score"] - 0.88) < 0.01
        assert body["error"] is None
        assert len(body["changes"]) == 1

    def test_optimization_with_api_error(self, client):
        fake = self._make_result(error="No API key provided")
        with patch("dbanalyser.ai_optimizer.optimizer.optimize_sql_object",
                   return_value=fake):
            r = client.post("/ai/optimize", json={
                "object_name": "usp_X",
                "sql": "SELECT 1",
            })
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is not None
        assert "api key" in body["error"].lower() or "No API key" in body["error"]

    def test_no_change_needed(self, client):
        fake = self._make_result(no_change_needed=True,
                                  no_change_reason="Already optimal.",
                                  optimized_sql=None, changes=[])
        with patch("dbanalyser.ai_optimizer.optimizer.optimize_sql_object",
                   return_value=fake):
            r = client.post("/ai/optimize", json={
                "object_name": "usp_Simple",
                "sql": "SELECT Id FROM Accounts WHERE Id = 1",
                "api_key": "sk-test",
            })
        assert r.status_code == 200
        body = r.json()
        assert body["no_change_needed"] is True
        assert body["no_change_reason"] == "Already optimal."

    def test_optimizer_exception_returns_500(self, client):
        with patch("dbanalyser.ai_optimizer.optimizer.optimize_sql_object",
                   side_effect=RuntimeError("unexpected")):
            r = client.post("/ai/optimize", json={
                "object_name": "usp_X", "sql": "SELECT 1",
            })
        assert r.status_code == 500

    def test_missing_sql_returns_422(self, client):
        r = client.post("/ai/optimize", json={"object_name": "usp_X"})
        assert r.status_code == 422


# ── GET /ai/optimizations ─────────────────────────────────────────────────────

class TestListOptimizations:
    def test_returns_list(self, client):
        with patch("dbanalyser.db.repository.get_ai_optimizations",
                   return_value=[_OPT_ROW]), \
             patch("dbanalyser.db.repository.count_ai_optimizations",
                   return_value=1):
            r = client.get("/ai/optimizations")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["optimizations"][0]["object_name"] == "usp_GetAccounts"

    def test_filter_by_object_name(self, client):
        captured = {}
        def fake_get(object_name=None, db_registry_id=None, limit=50, offset=0):
            captured["object_name"] = object_name
            return []
        with patch("dbanalyser.db.repository.get_ai_optimizations", fake_get), \
             patch("dbanalyser.db.repository.count_ai_optimizations", return_value=0):
            client.get("/ai/optimizations?object_name=usp_Get")
        assert captured["object_name"] == "usp_Get"

    def test_empty_history(self, client):
        with patch("dbanalyser.db.repository.get_ai_optimizations", return_value=[]), \
             patch("dbanalyser.db.repository.count_ai_optimizations", return_value=0):
            r = client.get("/ai/optimizations")
        assert r.json()["total"] == 0

    def test_pagination_params(self, client):
        captured = {}
        def fake_get(object_name=None, db_registry_id=None, limit=50, offset=0):
            captured.update({"limit": limit, "offset": offset})
            return []
        with patch("dbanalyser.db.repository.get_ai_optimizations", fake_get), \
             patch("dbanalyser.db.repository.count_ai_optimizations", return_value=0):
            client.get("/ai/optimizations?limit=10&offset=20")
        assert captured["limit"] == 10
        assert captured["offset"] == 20
