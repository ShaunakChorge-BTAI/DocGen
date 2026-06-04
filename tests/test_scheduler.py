"""
Tests for the scheduled scan engine (dbanalyser/scheduler/engine.py).
Database-dependent tests are skipped when PostgreSQL is not available.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dbanalyser.scheduler.engine import ScheduledTask, parse_next_run


# ─── parse_next_run ──────────────────────────────────────────────────────────

class TestParseNextRun:
    """Test schedule string → next datetime computation."""

    def _now(self, hour: int = 10, minute: int = 0) -> datetime:
        return datetime(2026, 3, 31, hour, minute, 0, tzinfo=timezone.utc)

    def test_hourly_returns_next_hour(self):
        now  = self._now(hour=10, minute=30)
        nxt  = parse_next_run("hourly", after=now)
        assert nxt.hour == 11
        assert nxt.minute == 0
        assert nxt.second == 0

    def test_daily_future_time_same_day(self):
        now  = self._now(hour=10)
        nxt  = parse_next_run("daily@14:00", after=now)
        assert nxt.hour == 14
        assert nxt.minute == 0
        assert nxt.day == now.day      # same day (14:00 > 10:00)

    def test_daily_past_time_next_day(self):
        from datetime import timedelta
        now  = self._now(hour=15)
        nxt  = parse_next_run("daily@08:00", after=now)
        # next run must be strictly after now (past 08:00 → tomorrow)
        assert nxt > now
        assert nxt.hour == 8 and nxt.minute == 0

    def test_weekly_correct_day(self):
        # 2026-03-31 is a Tuesday (weekday=1)
        now  = self._now(hour=10)
        nxt  = parse_next_run("weekly@fri@09:00", after=now)
        assert nxt.weekday() == 4     # Friday

    def test_weekly_past_day_advances_to_next_week(self):
        # Tuesday 10:00 → "weekly@mon@06:00" → next Monday
        now  = self._now(hour=10)
        nxt  = parse_next_run("weekly@mon@06:00", after=now)
        assert nxt.weekday() == 0     # Monday

    def test_manual_schedule_far_future(self):
        now = self._now()
        nxt = parse_next_run("manual", after=now)
        assert nxt.year >= now.year + 10

    def test_unknown_schedule_far_future(self):
        now = self._now()
        nxt = parse_next_run("every_other_sunday", after=now)
        assert nxt.year >= now.year + 10

    def test_next_run_always_after_now(self):
        now = datetime.now(timezone.utc)
        for schedule in ("hourly", "daily@02:00", "weekly@mon@06:00"):
            nxt = parse_next_run(schedule, after=now)
            assert nxt > now, f"next_run for '{schedule}' is not in the future"


# ─── ScheduledTask dataclass ─────────────────────────────────────────────────

class TestScheduledTask:
    def test_default_fields(self):
        task = ScheduledTask(db_name="LTFS_DEV", schedule="daily@02:00")
        assert task.enabled is True
        assert task.run_dmv is False
        assert task.formats == ["json"]
        assert task.label   == ""

    def test_custom_fields(self):
        task = ScheduledTask(
            db_name="LTFS_PROD", schedule="weekly@mon@06:00",
            label="nightly_sox", enabled=True, run_dmv=True,
            formats=["excel", "json"],
        )
        assert task.db_name  == "LTFS_PROD"
        assert task.run_dmv  is True
        assert "excel" in task.formats
