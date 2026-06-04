"""
Tests for /audit and /pipeline API routes.
All DB calls are mocked.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from unittest.mock import patch

import pytest
fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient

from dbanalyser.api.main import create_app

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    app = create_app(api_key="")
    return TestClient(app)


@dataclass
class _FakeAuditEntry:
    id:            int
    username:      str
    action:        str
    resource_type: str
    resource_id:   str
    details:       dict
    ip_address:    str
    created_at:    datetime


_AUDIT_ENTRY = _FakeAuditEntry(
    id=1, username="alice", action="optimize",
    resource_type="stored_procedure", resource_id="usp_GetAccounts",
    details={"model": "claude-3-5-haiku"}, ip_address="127.0.0.1",
    created_at=datetime(2026, 1, 1, 12, 0, 0),
)

_PIPELINE_ROW = {
    "id": 1, "run_id": 42, "step": "load_objects", "status": "completed",
    "started_at": datetime(2026, 1, 1, 12, 0, 0),
    "completed_at": datetime(2026, 1, 1, 12, 0, 5),
    "duration_sec": 5.0, "error": None, "details": {},
}


# ── GET /audit/ ───────────────────────────────────────────────────────────────

class TestAuditEndpoint:
    def test_returns_list(self, client):
        with patch("dbanalyser.audit.repository.get_audit_logs",
                   return_value=[_AUDIT_ENTRY]), \
             patch("dbanalyser.audit.repository.count_audit_logs",
                   return_value=1):
            r = client.get("/audit/")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["logs"][0]["username"] == "alice"
        assert body["logs"][0]["action"] == "optimize"

    def test_empty_log(self, client):
        with patch("dbanalyser.audit.repository.get_audit_logs", return_value=[]), \
             patch("dbanalyser.audit.repository.count_audit_logs", return_value=0):
            r = client.get("/audit/")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_filter_by_username(self, client):
        captured = {}
        def fake_get(username=None, action=None, resource_type=None,
                     limit=100, offset=0):
            captured["username"] = username
            return []
        with patch("dbanalyser.audit.repository.get_audit_logs", fake_get), \
             patch("dbanalyser.audit.repository.count_audit_logs", return_value=0):
            client.get("/audit/?username=alice")
        assert captured["username"] == "alice"

    def test_filter_by_action(self, client):
        captured = {}
        def fake_get(username=None, action=None, resource_type=None,
                     limit=100, offset=0):
            captured["action"] = action
            return []
        with patch("dbanalyser.audit.repository.get_audit_logs", fake_get), \
             patch("dbanalyser.audit.repository.count_audit_logs", return_value=0):
            client.get("/audit/?action=login")
        assert captured["action"] == "login"

    def test_pagination(self, client):
        captured = {}
        def fake_get(username=None, action=None, resource_type=None,
                     limit=100, offset=0):
            captured.update({"limit": limit, "offset": offset})
            return []
        with patch("dbanalyser.audit.repository.get_audit_logs", fake_get), \
             patch("dbanalyser.audit.repository.count_audit_logs", return_value=0):
            client.get("/audit/?limit=25&offset=50")
        assert captured["limit"] == 25
        assert captured["offset"] == 50

    def test_response_has_limit_and_offset(self, client):
        with patch("dbanalyser.audit.repository.get_audit_logs", return_value=[]), \
             patch("dbanalyser.audit.repository.count_audit_logs", return_value=0):
            r = client.get("/audit/?limit=20&offset=5")
        body = r.json()
        assert body["limit"] == 20
        assert body["offset"] == 5


# ── GET /pipeline/{run_id} ───────────────────────────────────────────────────

class TestPipelineEndpoint:
    def test_returns_steps(self, client):
        with patch("dbanalyser.db.repository.get_pipeline_steps",
                   return_value=[_PIPELINE_ROW]):
            r = client.get("/pipeline/42")
        assert r.status_code == 200
        body = r.json()
        assert body["run_id"] == 42
        assert body["total"] == 1
        assert body["steps"][0]["step"] == "load_objects"
        assert body["steps"][0]["status"] == "completed"
        assert body["steps"][0]["duration_sec"] == 5.0

    def test_empty_pipeline(self, client):
        with patch("dbanalyser.db.repository.get_pipeline_steps", return_value=[]):
            r = client.get("/pipeline/99")
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["run_id"] == 99

    def test_multiple_steps(self, client):
        steps = [
            {**_PIPELINE_ROW, "id": i, "step": f"step_{i}"}
            for i in range(1, 6)
        ]
        with patch("dbanalyser.db.repository.get_pipeline_steps", return_value=steps):
            r = client.get("/pipeline/1")
        assert r.json()["total"] == 5

    def test_step_with_error(self, client):
        row = {**_PIPELINE_ROW, "status": "failed", "error": "Connection refused"}
        with patch("dbanalyser.db.repository.get_pipeline_steps", return_value=[row]):
            r = client.get("/pipeline/1")
        step = r.json()["steps"][0]
        assert step["status"] == "failed"
        assert step["error"] == "Connection refused"
