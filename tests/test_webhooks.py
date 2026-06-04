"""
Tests for webhook notification module (dbanalyser/notifications/webhooks.py).
All HTTP calls are mocked — no live network required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dbanalyser.notifications.webhooks import (
    WebhookPayload,
    _build_slack_payload,
    _build_teams_payload,
    send_notifications,
    send_slack,
    send_teams,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _payload(**kwargs) -> WebhookPayload:
    defaults = dict(
        db_name        = "LTFS_PROD",
        run_label      = "nightly_20260331",
        health_score   = 62.5,
        total_findings = 10,
        severity_counts= {"Critical": 2, "High": 3, "Medium": 5, "Low": 0},
        critical_findings=[
            {"object_name": "usp_ProcessPayment", "issue": "UPDATE without WHERE"},
            {"object_name": "usp_PostLedger",     "issue": "Missing XACT_ABORT"},
        ],
        run_url        = "http://localhost:8501",
        environment    = "production",
    )
    defaults.update(kwargs)
    return WebhookPayload(**defaults)


def _cfg(
    enabled:               bool = True,
    slack_webhook_url:     str  = "https://hooks.slack.com/test",
    teams_webhook_url:     str  = "",
    alert_on_severity:     list = None,
    min_findings_to_alert: int  = 1,
):
    class Cfg:
        pass
    c = Cfg()
    c.enabled               = enabled
    c.slack_webhook_url     = slack_webhook_url
    c.teams_webhook_url     = teams_webhook_url
    c.alert_on_severity     = alert_on_severity or ["Critical", "High"]
    c.min_findings_to_alert = min_findings_to_alert
    c.include_summary       = True
    return c


# ─── Payload builders ────────────────────────────────────────────────────────

class TestBuildSlackPayload:
    def test_contains_db_name(self):
        p   = _payload()
        msg = _build_slack_payload(p)
        text = str(msg)
        assert "LTFS_PROD" in text

    def test_health_emoji_red_below_50(self):
        p   = _payload(health_score=40)
        msg = _build_slack_payload(p)
        assert "🔴" in str(msg)

    def test_health_emoji_green_above_85(self):
        p   = _payload(health_score=90)
        msg = _build_slack_payload(p)
        assert "🟢" in str(msg)

    def test_critical_findings_included(self):
        p   = _payload()
        msg = _build_slack_payload(p)
        assert "usp_ProcessPayment" in str(msg)

    def test_run_url_action_block_present(self):
        p   = _payload(run_url="http://dash:8501")
        msg = _build_slack_payload(p)
        assert "http://dash:8501" in str(msg)

    def test_no_run_url_no_action_block(self):
        p   = _payload(run_url=None)
        msg = _build_slack_payload(p)
        # actions block should not be present
        blocks = msg.get("blocks", [])
        action_blocks = [b for b in blocks if b.get("type") == "actions"]
        assert len(action_blocks) == 0

    def test_structure_has_blocks(self):
        p   = _payload()
        msg = _build_slack_payload(p)
        assert "blocks" in msg
        assert isinstance(msg["blocks"], list)


class TestBuildTeamsPayload:
    def test_contains_db_name(self):
        p   = _payload()
        msg = _build_teams_payload(p)
        assert "LTFS_PROD" in str(msg)

    def test_facts_include_health(self):
        p   = _payload()
        msg = _build_teams_payload(p)
        assert "62.5" in str(msg)

    def test_critical_findings_in_body(self):
        p   = _payload()
        msg = _build_teams_payload(p)
        assert "usp_ProcessPayment" in str(msg)

    def test_adaptive_card_schema(self):
        p   = _payload()
        msg = _build_teams_payload(p)
        assert msg.get("type") == "message"
        card = msg["attachments"][0]["content"]
        assert card["type"] == "AdaptiveCard"


# ─── send_notifications ──────────────────────────────────────────────────────

class TestSendNotifications:
    def test_disabled_does_not_call_post(self):
        cfg = _cfg(enabled=False)
        with patch("dbanalyser.notifications.webhooks._post_json") as mock_post:
            send_notifications(cfg, _payload())
        mock_post.assert_not_called()

    def test_threshold_not_met_no_post(self):
        # Only Low findings — threshold requires Critical/High
        p   = _payload(severity_counts={"Critical": 0, "High": 0, "Medium": 5, "Low": 10},
                       total_findings=15)
        cfg = _cfg(enabled=True, min_findings_to_alert=1)
        with patch("dbanalyser.notifications.webhooks._post_json") as mock_post:
            send_notifications(cfg, p)
        mock_post.assert_not_called()

    def test_slack_called_when_url_set(self):
        cfg = _cfg(enabled=True, slack_webhook_url="https://hooks.slack.com/test")
        with patch("dbanalyser.notifications.webhooks._post_json", return_value=True) as mock:
            send_notifications(cfg, _payload())
        mock.assert_called_once()
        assert "hooks.slack.com" in mock.call_args[0][0]

    def test_teams_called_when_url_set(self):
        cfg = _cfg(enabled=True, slack_webhook_url="",
                   teams_webhook_url="https://outlook.office.com/webhook/test")
        with patch("dbanalyser.notifications.webhooks._post_json", return_value=True) as mock:
            send_notifications(cfg, _payload())
        mock.assert_called_once()
        assert "outlook.office.com" in mock.call_args[0][0]

    def test_both_webhooks_called(self):
        cfg = _cfg(enabled=True,
                   slack_webhook_url="https://hooks.slack.com/test",
                   teams_webhook_url="https://outlook.office.com/webhook/test")
        with patch("dbanalyser.notifications.webhooks._post_json", return_value=True) as mock:
            send_notifications(cfg, _payload())
        assert mock.call_count == 2

    def test_send_slack_returns_true_on_success(self):
        with patch("dbanalyser.notifications.webhooks._post_json", return_value=True):
            result = send_slack("https://hooks.slack.com/test", _payload())
        assert result is True

    def test_send_teams_returns_false_on_failure(self):
        with patch("dbanalyser.notifications.webhooks._post_json", return_value=False):
            result = send_teams("https://outlook.office.com/webhook/test", _payload())
        assert result is False

    def test_no_urls_configured_no_error(self):
        cfg = _cfg(enabled=True, slack_webhook_url="", teams_webhook_url="")
        # Should not raise, just log a warning
        with patch("dbanalyser.notifications.webhooks._post_json") as mock_post:
            send_notifications(cfg, _payload())
        mock_post.assert_not_called()
