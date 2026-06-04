"""
Tests for drift detection and findings deduplication repository functions.
All DB interactions are mocked via a fake cursor/connection.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

# ── stub psycopg2 so the repository module can be imported without a DB ──────
if "psycopg2" not in sys.modules:
    _psyco_mock = MagicMock()
    _pool_mock  = MagicMock()
    _extra_mock = MagicMock()
    _extra_mock.execute_values = MagicMock()
    _extra_mock.RealDictCursor = MagicMock()
    _psyco_mock.pool   = _pool_mock
    _psyco_mock.extras = _extra_mock
    sys.modules["psycopg2"]        = _psyco_mock
    sys.modules["psycopg2.pool"]   = _pool_mock
    sys.modules["psycopg2.extras"] = _extra_mock


# ── helpers ──────────────────────────────────────────────────────────────────

class FakeCursor:
    """Minimal cursor stub that records execute calls and returns configurable rows."""

    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount
        self.calls: list = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class FakeConn:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


@contextmanager
def _mock_conn(fake_cursor):
    """Patch get_conn and get_cursor with the given fake cursor."""
    fake_conn = FakeConn(fake_cursor)
    with patch("dbanalyser.db.repository.get_conn", return_value=fake_conn), \
         patch("dbanalyser.db.repository.get_cursor") as mock_gc:
        mock_gc.return_value.__enter__ = lambda s: fake_cursor
        mock_gc.return_value.__exit__ = lambda s, *a: None
        yield fake_cursor


# ── detect_and_mark_content_drift ────────────────────────────────────────────

class TestDetectAndMarkContentDrift:
    def test_returns_zero_when_no_prior_run(self):
        """When no previous run exists, nothing is marked drifted."""
        from dbanalyser.db.repository import detect_and_mark_content_drift
        # fetchone returns None → no prior run found
        cur = FakeCursor(rows=[None], rowcount=0)
        with _mock_conn(cur):
            result = detect_and_mark_content_drift(run_id=10, db_registry_id=5)
        assert result == 0

    def test_returns_rowcount_when_objects_changed(self):
        """When prior run exists and objects changed, rowcount is returned."""
        from dbanalyser.db.repository import detect_and_mark_content_drift

        # fetchone returns a prior run row as tuple (id=9); UPDATE affects 3 rows
        cur = FakeCursor(rows=[(9,)], rowcount=3)
        with _mock_conn(cur):
            result = detect_and_mark_content_drift(run_id=10, db_registry_id=5)
        assert result == 3

    def test_file_mode_uses_null_db_registry(self):
        """Without db_registry_id, the query should not filter by db_registry_id."""
        from dbanalyser.db.repository import detect_and_mark_content_drift
        cur = FakeCursor(rows=[None], rowcount=0)
        with _mock_conn(cur):
            result = detect_and_mark_content_drift(run_id=10, db_registry_id=None)
        # Should not raise; SELECT query must not reference db_registry_id
        assert result == 0
        first_sql = cur.calls[0][0]
        assert "db_registry_id IS NULL" in first_sql

    def test_returns_zero_on_exception(self):
        """Database errors should be swallowed, returning 0."""
        from dbanalyser.db.repository import detect_and_mark_content_drift
        with patch("dbanalyser.db.repository.get_conn",
                   side_effect=Exception("db down")):
            result = detect_and_mark_content_drift(run_id=10, db_registry_id=5)
        assert result == 0


# ── enrich_findings_with_history ─────────────────────────────────────────────

class TestEnrichFindingsWithHistory:
    def test_returns_rowcount_of_deduped_findings(self):
        """When repeated findings are found, rowcount is returned."""
        from dbanalyser.db.repository import enrich_findings_with_history
        cur = FakeCursor(rows=[], rowcount=7)
        with _mock_conn(cur):
            result = enrich_findings_with_history(run_id=10, db_registry_id=5)
        assert result == 7

    def test_file_mode_dedup(self):
        """Without db_registry_id, the non-join path is taken."""
        from dbanalyser.db.repository import enrich_findings_with_history
        cur = FakeCursor(rows=[], rowcount=2)
        with _mock_conn(cur):
            result = enrich_findings_with_history(run_id=10, db_registry_id=None)
        assert result == 2
        # Should have executed at least 2 statements (last_seen_run + dedup)
        assert len(cur.calls) >= 2

    def test_always_sets_last_seen_run(self):
        """The first SQL executed must update last_seen_run."""
        from dbanalyser.db.repository import enrich_findings_with_history
        cur = FakeCursor(rows=[], rowcount=0)
        with _mock_conn(cur):
            enrich_findings_with_history(run_id=42, db_registry_id=5)
        first_sql = cur.calls[0][0]
        assert "last_seen_run" in first_sql

    def test_returns_zero_on_exception(self):
        """Database errors should be swallowed."""
        from dbanalyser.db.repository import enrich_findings_with_history
        with patch("dbanalyser.db.repository.get_conn",
                   side_effect=Exception("connection refused")):
            result = enrich_findings_with_history(run_id=10, db_registry_id=5)
        assert result == 0


# ── repository functions: insert / get ai_optimizations ──────────────────────

class TestAiOptimizationsRepository:
    def test_insert_returns_id(self):
        from dbanalyser.db.repository import insert_ai_optimization
        cur = FakeCursor(rows=[(99,)], rowcount=1)
        with _mock_conn(cur):
            row_id = insert_ai_optimization(
                object_name="usp_X", original_sql="SELECT *",
                optimized_sql="SELECT Id", reasoning="Better",
                schema_context_used="ctx", execution_plan_used="",
                findings_used=[], confidence_score=0.9,
                model_used="claude-haiku", tokens_used=300,
            )
        assert row_id == 99

    def test_insert_returns_minus_one_on_error(self):
        from dbanalyser.db.repository import insert_ai_optimization
        with patch("dbanalyser.db.repository.get_conn",
                   side_effect=Exception("db error")):
            row_id = insert_ai_optimization(
                object_name="usp_X", original_sql="SELECT *",
                optimized_sql="SELECT Id", reasoning="Better",
                schema_context_used="", execution_plan_used="",
                findings_used=[], confidence_score=0.0,
                model_used="", tokens_used=0,
            )
        assert row_id == -1

    def test_get_returns_empty_on_error(self):
        from dbanalyser.db.repository import get_ai_optimizations
        with patch("dbanalyser.db.repository.get_cursor",
                   side_effect=Exception("db error")):
            rows = get_ai_optimizations()
        assert rows == []


# ── repository functions: pipeline_steps ─────────────────────────────────────

class TestPipelineStepsRepository:
    def test_insert_pipeline_step_returns_id(self):
        from dbanalyser.db.repository import insert_pipeline_step
        cur = FakeCursor(rows=[(5,)], rowcount=1)
        with _mock_conn(cur):
            step_id = insert_pipeline_step(run_id=1, step="load_objects")
        assert step_id == 5

    def test_insert_returns_minus_one_on_error(self):
        from dbanalyser.db.repository import insert_pipeline_step
        with patch("dbanalyser.db.repository.get_conn",
                   side_effect=Exception("db error")):
            step_id = insert_pipeline_step(run_id=1, step="load_objects")
        assert step_id == -1

    def test_get_pipeline_steps_returns_empty_on_error(self):
        from dbanalyser.db.repository import get_pipeline_steps
        with patch("dbanalyser.db.repository.get_cursor",
                   side_effect=Exception("db error")):
            steps = get_pipeline_steps(run_id=1)
        assert steps == []
