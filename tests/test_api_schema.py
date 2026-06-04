"""
Tests for /schema API routes.
All DB / schema_intel calls are mocked — no PostgreSQL required.
"""
from __future__ import annotations

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


_OBJ = {
    "id": 1, "db_registry_id": 10, "object_type": "table",
    "schema_name": "dbo", "object_name": "Accounts",
    "parent_name": "", "data_type": None, "is_nullable": None,
    "is_primary_key": False, "is_foreign_key": False,
    "definition": "CREATE TABLE dbo.Accounts (Id INT)", "ingested_at": None,
}


# ── GET /schema/ ──────────────────────────────────────────────────────────────

class TestListSchemaObjects:
    def test_returns_list(self, client):
        with patch("dbanalyser.schema_intel.repository.list_schema_objects",
                   return_value=[_OBJ]):
            r = client.get("/schema/")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["objects"][0]["object_name"] == "Accounts"

    def test_empty_list(self, client):
        with patch("dbanalyser.schema_intel.repository.list_schema_objects",
                   return_value=[]):
            r = client.get("/schema/")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_filter_by_db_registry_id(self, client):
        captured = {}
        def fake_list(db_registry_id=None, object_type=None, limit=200):
            captured["db_registry_id"] = db_registry_id
            return []
        with patch("dbanalyser.schema_intel.repository.list_schema_objects", fake_list):
            client.get("/schema/?db_registry_id=5")
        assert captured["db_registry_id"] == 5

    def test_filter_by_object_type(self, client):
        captured = {}
        def fake_list(db_registry_id=None, object_type=None, limit=200):
            captured["object_type"] = object_type
            return []
        with patch("dbanalyser.schema_intel.repository.list_schema_objects", fake_list):
            client.get("/schema/?object_type=view")
        assert captured["object_type"] == "view"


# ── POST /schema/search ───────────────────────────────────────────────────────

class TestSearchSchema:
    def test_basic_search(self, client):
        mock_result = [
            {"object_type": "table", "schema_name": "dbo",
             "object_name": "Accounts", "parent_name": "",
             "definition": "accounts", "similarity_score": 0.92},
        ]
        with patch("dbanalyser.schema_intel.searcher.search_schema",
                   return_value=mock_result):
            r = client.post("/schema/search", json={"query": "accounts"})
        assert r.status_code == 200
        body = r.json()
        assert body["query"] == "accounts"
        assert body["total"] == 1
        assert abs(body["results"][0]["similarity_score"] - 0.92) < 0.01

    def test_empty_results(self, client):
        with patch("dbanalyser.schema_intel.searcher.search_schema", return_value=[]):
            r = client.post("/schema/search", json={"query": "nonexistent"})
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_top_k_respected(self, client):
        captured = {}
        def fake_search(query, top_k=10, min_score=0.0, object_types=None,
                        db_registry_id=None):
            captured["top_k"] = top_k
            return []
        with patch("dbanalyser.schema_intel.searcher.search_schema", fake_search):
            client.post("/schema/search", json={"query": "x", "top_k": 5})
        assert captured["top_k"] == 5

    def test_search_error_returns_500(self, client):
        with patch("dbanalyser.schema_intel.searcher.search_schema",
                   side_effect=RuntimeError("db down")):
            r = client.post("/schema/search", json={"query": "fail"})
        assert r.status_code == 500


# ── GET /schema/summary ───────────────────────────────────────────────────────

class TestSchemaSummary:
    def test_returns_counts(self, client):
        with patch("dbanalyser.schema_intel.repository.get_schema_summary",
                   return_value={"table": 10, "column": 100, "procedure": 5}):
            r = client.get("/schema/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 115
        assert body["counts"]["table"] == 10

    def test_empty_schema(self, client):
        with patch("dbanalyser.schema_intel.repository.get_schema_summary",
                   return_value={}):
            r = client.get("/schema/summary")
        assert r.json()["total"] == 0


# ── DELETE /schema/{db_registry_id} ──────────────────────────────────────────

class TestClearSchema:
    def test_delete_returns_ok(self, client):
        with patch("dbanalyser.schema_intel.repository.delete_schema_for_db",
                   return_value=42):
            r = client.delete("/schema/10")
        assert r.status_code == 200
        assert "42" in r.json()["message"]
