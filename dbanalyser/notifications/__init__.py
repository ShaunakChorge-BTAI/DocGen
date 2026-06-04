"""Webhook notification package (Slack, Microsoft Teams)."""
from .webhooks import WebhookPayload, send_notifications, send_slack, send_teams

__all__ = ["WebhookPayload", "send_notifications", "send_slack", "send_teams"]
