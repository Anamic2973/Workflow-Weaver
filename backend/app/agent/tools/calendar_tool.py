"""
Google Calendar tool wrapper.

Reuses the same gdrive-mcp container as gdrive_tool.py — the underlying
@piotr-agier/google-drive-mcp package bundles Calendar tools too, and the
OAuth token already carries the `calendar.events` scope, so no separate
container or auth step is needed.

Same session-per-call pattern as notion_tool.py/gdrive_tool.py: a session
must not outlive the task that created it, so we open and close one per
call. Responses are formatted text, not JSON — parsed with regex like
gdrive_tool.py's create_document.
"""
from __future__ import annotations

import re
from typing import Any

_EVENT_ID_RE = re.compile(r"^Event ID:\s*(\S+)", re.MULTILINE)
_LINK_RE = re.compile(r"^Link:\s*(\S+)", re.MULTILINE)


def _server_params():
    from mcp import StdioServerParameters

    return StdioServerParameters(
        command="docker",
        args=["exec", "-i", "gdrive-mcp", "npx", "-y", "@piotr-agier/google-drive-mcp"],
    )


async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)

    text = result.content[0].text if result.content else ""
    if result.isError:
        raise RuntimeError(f"Calendar MCP tool '{tool_name}' failed: {text}")
    return text


async def create_event(
    summary: str,
    start: str,
    end: str,
    description: str | None = None,
    attendees: list[str] | None = None,
    time_zone: str = "Asia/Kolkata",
) -> dict[str, Any]:
    """Create a calendar event. start/end are RFC3339 datetimes without offset (e.g. '2026-08-15T15:00:00')."""
    text = await _call_tool(
        "createCalendarEvent",
        {
            "summary": summary,
            "start": {"dateTime": start, "timeZone": time_zone},
            "end": {"dateTime": end, "timeZone": time_zone},
            **({"description": description} if description else {}),
            **({"attendees": attendees} if attendees else {}),
        },
    )
    event_id_match, link_match = _EVENT_ID_RE.search(text), _LINK_RE.search(text)
    if not event_id_match:
        raise RuntimeError(f"createCalendarEvent succeeded but no event ID found in response: {text}")
    return {"event_id": event_id_match.group(1), "url": link_match.group(1) if link_match else None, "summary": summary}


async def delete_event(event_id: str) -> dict[str, Any]:
    """Rollback: cancel a calendar event created earlier in the same run."""
    await _call_tool("deleteCalendarEvent", {"eventId": event_id})
    return {"event_id": event_id, "deleted": True}
