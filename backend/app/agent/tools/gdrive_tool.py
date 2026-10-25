"""
Google Drive MCP client wrapper.

Uses @piotr-agier/google-drive-mcp (OAuth 2.0, actively maintained) rather
than the deprecated @modelcontextprotocol/server-gdrive, which is read-only
(search only) and can't create files at all.

This server's OAuth flow needs a real browser, which a `docker exec`
session can't provide — so the one-time `auth` step is run on the host
(see README), producing gdrive-tokens.json, which is then mounted into the
container read-write (the server refreshes the access token in place).
Regular tool calls after that don't need a browser and work fine via
`docker exec`.

Same session-per-call pattern as notion_tool.py: a session must not outlive
the task that created it, so we open and close one per call.
"""
from __future__ import annotations

import re
from typing import Any

from app.config import settings

# This server replies with a formatted text message, not JSON, e.g.:
#   "Created Google Doc: <name>\nID: <id>\nLink: <url>"
_ID_RE = re.compile(r"^ID:\s*(\S+)", re.MULTILINE)
_LINK_RE = re.compile(r"^Link:\s*(\S+)", re.MULTILINE)


def _server_params():
    from mcp import StdioServerParameters

    return StdioServerParameters(
        command="docker",
        args=["exec", "-i", "gdrive-mcp", "npx", "-y", "@piotr-agier/google-drive-mcp"],
    )


async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Returns the tool's raw text reply — this server responds with a
    formatted message, not JSON, so callers parse what they need out of it."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)

    text = result.content[0].text if result.content else ""
    if result.isError:
        raise RuntimeError(f"Google Drive MCP tool '{tool_name}' failed: {text}")
    return text


async def create_document(title: str, content: str, folder_id: str | None = None) -> dict[str, Any]:
    """
    Create a Google Doc from `content`, which may be plain text or simple
    HTML (h1-h3, p, ul/ol/li, b/i, table) — HTML renders with real headings/
    lists/formatting instead of one flat text blob. Returns file_id/url for
    rollback.
    """
    target_folder = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
    html = content if "<" in content and ">" in content else f"<p>{content}</p>"
    text = await _call_tool(
        "createDocFromHTML",
        {"name": title, "html": html, "parentFolderId": target_folder},
    )
    id_match, link_match = _ID_RE.search(text), _LINK_RE.search(text)
    if not id_match:
        raise RuntimeError(f"createGoogleDoc succeeded but no doc ID found in response: {text}")
    return {"file_id": id_match.group(1), "url": link_match.group(1) if link_match else None, "title": title}


async def delete_document(file_id: str) -> dict[str, Any]:
    """Rollback: move a file to trash."""
    await _call_tool("deleteItem", {"itemId": file_id})
    return {"file_id": file_id, "deleted": True}
