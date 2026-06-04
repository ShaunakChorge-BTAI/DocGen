"""
Slack and Microsoft Teams Webhook Notifications
================================================
Sends alert payloads to Slack Incoming Webhooks and Teams Adaptive Card webhooks
when analysis findings exceed configured thresholds.

Configuration (analysis_config.yaml):
  notifications:
    enabled: true
    slack_webhook_url: "https://hooks.slack.com/services/T.../B.../..."
    teams_webhook_url: "https://outlook.office.com/webhook/..."
    alert_on_severity: [Critical, High]
    min_findings_to_alert: 1
    include_summary: true
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


# ─── Payload dataclass ────────────────────────────────────────────────────────

@dataclass
class WebhookPayload:
    """Summary data passed to webhook senders after an analysis run."""
    db_name:          str
    run_label:        str
    health_score:     float
    total_findings:   int
    severity_counts:  Dict[str, int]
    critical_findings: List[dict] = field(default_factory=list)   # first N critical findings
    run_url:          Optional[str] = None
    environment:      str = "development"


# ─── HTTP helper ──────────────────────────────────────────────────────────────

def _post_json(url: str, payload: dict, timeout: int = 10) -> bool:
    """POST a JSON payload to a URL.  Returns True on HTTP 2xx."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except Exception as exc:
        log.warning("Webhook POST to %s failed: %s", url, exc)
        return False


# ─── Slack payload builder ────────────────────────────────────────────────────

def _build_slack_payload(p: WebhookPayload) -> dict:
    sev = p.severity_counts
    health_emoji = (
        "🔴" if p.health_score < 50 else
        "🟠" if p.health_score < 70 else
        "🟡" if p.health_score < 85 else
        "🟢"
    )
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text",
                     "text": f"DBAnalyser Alert — {p.db_name}",
                     "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Run:*\n{p.run_label}"},
                {"type": "mrkdwn",
                 "text": f"*Health Score:*\n{health_emoji} {p.health_score:.1f}/100"},
                {"type": "mrkdwn", "text": f"*Environment:*\n{p.environment}"},
                {"type": "mrkdwn",
                 "text": (f"*Findings:*\n{p.total_findings} total  |  "
                          f"{sev.get('Critical', 0)} critical  |  "
                          f"{sev.get('High', 0)} high")},
            ],
        },
    ]
    if p.critical_findings:
        text = "\n".join(
            f"• `{f.get('object_name', '?')}` — {f.get('issue', '?')[:80]}"
            for f in p.critical_findings[:5]
        )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": f"*Critical Findings (first 5):*\n{text}"},
        })
    if p.run_url:
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "View Report in Dashboard"},
                "url": p.run_url,
                "style": "primary",
            }],
        })
    blocks.append({"type": "divider"})
    return {"blocks": blocks}


# ─── Teams payload builder ────────────────────────────────────────────────────

def _build_teams_payload(p: WebhookPayload) -> dict:
    sev = p.severity_counts
    health_colour = (
        "attention" if p.health_score < 50 else
        "warning"   if p.health_score < 70 else
        "default"
    )
    facts = [
        {"title": "Run",         "value": p.run_label},
        {"title": "Environment", "value": p.environment},
        {"title": "Health",      "value": f"{p.health_score:.1f}/100"},
        {"title": "Total",       "value": str(p.total_findings)},
        {"title": "Critical",    "value": str(sev.get("Critical", 0))},
        {"title": "High",        "value": str(sev.get("High", 0))},
        {"title": "Medium",      "value": str(sev.get("Medium", 0))},
    ]
    body = [
        {
            "type": "TextBlock",
            "text": f"DBAnalyser Alert — {p.db_name}",
            "weight": "Bolder", "size": "Large", "color": health_colour,
        },
        {"type": "FactSet", "facts": facts},
    ]
    if p.critical_findings:
        items = "\n\n".join(
            f"**{f.get('object_name', '?')}**: {f.get('issue', '?')[:100]}"
            for f in p.critical_findings[:5]
        )
        body.append({
            "type": "TextBlock",
            "text": f"**Critical Findings (first 5):**\n\n{items}",
            "wrap": True,
        })
    card: dict = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": body,
            },
        }],
    }
    if p.run_url:
        card["attachments"][0]["content"]["actions"] = [{
            "type": "Action.OpenUrl",
            "title": "View Report in Dashboard",
            "url": p.run_url,
        }]
    return card


# ─── Public API ───────────────────────────────────────────────────────────────

def send_slack(url: str, payload: WebhookPayload) -> bool:
    """Send a Slack Incoming Webhook notification.  Returns True on success."""
    return _post_json(url, _build_slack_payload(payload))


def send_teams(url: str, payload: WebhookPayload) -> bool:
    """Send a Microsoft Teams Adaptive Card notification.  Returns True on success."""
    return _post_json(url, _build_teams_payload(payload))


def send_notifications(cfg_notif, payload: WebhookPayload) -> None:
    """
    Evaluate threshold conditions and fire configured webhooks.

    Args:
        cfg_notif : NotificationsConfig from Settings.
        payload   : WebhookPayload with run summary data.
    """
    if not getattr(cfg_notif, "enabled", False):
        return

    alert_sevs   = set(getattr(cfg_notif, "alert_on_severity", ["Critical", "High"]))
    triggered    = sum(v for k, v in payload.severity_counts.items() if k in alert_sevs)
    min_findings = getattr(cfg_notif, "min_findings_to_alert", 1)

    if triggered < min_findings:
        log.debug(
            "Notification threshold not met: %d matching finding(s) < min %d",
            triggered, min_findings,
        )
        return

    log.info(
        "Sending webhook notifications for run '%s' (%d alert-severity finding(s))",
        payload.run_label, triggered,
    )

    slack_url = getattr(cfg_notif, "slack_webhook_url", "") or ""
    teams_url = getattr(cfg_notif, "teams_webhook_url", "") or ""

    if slack_url:
        ok = send_slack(slack_url, payload)
        log.info("Slack notification: %s", "sent" if ok else "FAILED")

    if teams_url:
        ok = send_teams(teams_url, payload)
        log.info("Teams notification: %s", "sent" if ok else "FAILED")

    if not slack_url and not teams_url:
        log.warning(
            "Notifications enabled but no webhook URLs configured "
            "(slack_webhook_url and teams_webhook_url are both empty)."
        )
