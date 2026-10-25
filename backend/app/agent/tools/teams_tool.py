"""
Microsoft Teams notifications via Incoming Webhook / Workflow webhook.

No MCP server needed here — Teams webhooks are a simple authenticated POST.
Note: Teams messages cannot be rolled back once posted (no delete API for
incoming webhooks), so this tool is intentionally excluded from the
rollback plan; on rollback the graph instead posts a follow-up correction
message (see `post_correction`).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


def _adaptive_card(title: str, text: str, facts: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium"},
                        {"type": "TextBlock", "text": text, "wrap": True},
                        *(
                            [
                                {
                                    "type": "FactSet",
                                    "facts": [{"title": k, "value": v} for k, v in facts],
                                }
                            ]
                            if facts
                            else []
                        ),
                    ],
                },
            }
        ],
    }


async def post_message(title: str, text: str, facts: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Post a workflow update/summary card to the configured Teams channel."""
    payload = _adaptive_card(title, text, facts)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.TEAMS_WEBHOOK_URL, json=payload)
        resp.raise_for_status()
    return {"posted": True, "title": title}


async def post_correction(original_title: str, reason: str) -> dict[str, Any]:
    """Used during rollback: Teams messages can't be deleted, so we post a correction instead."""
    return await post_message(
        title=f"⚠️ Correction: {original_title}",
        text=f"This workflow run failed after this notification was sent. Reason: {reason}. "
        f"Any related Notion/Drive artifacts have been rolled back.",
    )
