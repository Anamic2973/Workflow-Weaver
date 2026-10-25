"""
Notion MCP client wrapper.

Talks to a running Notion MCP server (see docker-compose / MCP docs) using
the MCP Python client. Exposes coroutine functions the LangGraph nodes call
directly, each returning a JSON-serializable result and raising on failure
so the graph's retry/rollback logic can catch it.

Tool names/argument shapes below mirror the Notion REST API 1:1 (this MCP
server is generated from Notion's OpenAPI spec) — confirmed against the
live server's `list_tools()`/`inputSchema`, not guessed.
"""
from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Any

from app.config import settings

_HEADING_TAGS = {"h1": "heading_1", "h2": "heading_2", "h3": "heading_3"}
_LIST_ITEM_TAGS = {"ul": "bulleted_list_item", "ol": "numbered_list_item"}


class _HtmlToNotionBlocks(HTMLParser):
    """
    Converts a small subset of HTML (h1-h3, p, ul/ol/li, b/strong, i/em) into
    Notion block objects. The planner is asked to produce this same subset
    for page content, so pages come out with real headings/lists instead of
    one flat paragraph.
    """

    def __init__(self):
        super().__init__()
        self.blocks: list[dict[str, Any]] = []
        self._block_type: str | None = None
        self._list_item_type: str | None = None
        self._segments: list[dict[str, Any]] = []
        self._bold = False
        self._italic = False

    def handle_starttag(self, tag, attrs):
        if tag in _HEADING_TAGS or tag == "p":
            self._block_type = _HEADING_TAGS.get(tag, "paragraph")
        elif tag in _LIST_ITEM_TAGS:
            self._list_item_type = _LIST_ITEM_TAGS[tag]
        elif tag == "li":
            self._block_type = self._list_item_type or "bulleted_list_item"
        elif tag in ("b", "strong"):
            self._bold = True
        elif tag in ("i", "em"):
            self._italic = True

    def handle_endtag(self, tag):
        if tag in _HEADING_TAGS or tag in ("p", "li"):
            self._flush_block()
        elif tag in ("b", "strong"):
            self._bold = False
        elif tag in ("i", "em"):
            self._italic = False

    def handle_data(self, data):
        if not data.strip():
            return
        self._segments.append({
            "type": "text",
            "text": {"content": data},
            "annotations": {"bold": self._bold, "italic": self._italic},
        })

    def _flush_block(self):
        if self._segments and self._block_type:
            self.blocks.append({
                "object": "block",
                "type": self._block_type,
                self._block_type: {"rich_text": self._segments},
            })
        self._segments = []
        self._block_type = None

    def close(self):
        super().close()
        self._flush_block()


def _html_to_blocks(html: str) -> list[dict[str, Any]]:
    parser = _HtmlToNotionBlocks()
    parser.feed(html)
    parser.close()
    if not parser.blocks:
        # Plain text with no HTML tags — fall back to a single paragraph.
        return [_rich_text_block("paragraph", html)]
    return parser.blocks


def _server_params():
    """
    The Notion MCP server runs inside the `notion-mcp` container started by
    docker-compose.yml (see repo root). We attach to it via `docker exec -i`
    so stdin/stdout act as the MCP stdio transport; NOTION_TOKEN is already
    set in the container's environment, so it doesn't need to be re-passed.
    """
    from mcp import StdioServerParameters

    return StdioServerParameters(
        command="docker",
        args=["exec", "-i", "notion-mcp", "npx", "-y", "@notionhq/notion-mcp-server"],
    )


async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Opens a fresh MCP session, calls one tool, and tears the session down —
    all within the caller's task. A session must not outlive the task that
    created it (the stdio transport's task group is task-scoped), so we
    don't cache one across calls. Notion's MCP tools return the raw Notion
    API response as a JSON string in the first content block.
    """
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)

    text = result.content[0].text if result.content else "{}"
    parsed = json.loads(text)
    # The Notion MCP server doesn't always set isError=True for API-level
    # failures — it can return the Notion error envelope as "successful"
    # content instead, so check the payload shape too.
    if result.isError or (isinstance(parsed, dict) and parsed.get("object") == "error"):
        raise RuntimeError(f"Notion MCP tool '{tool_name}' failed: {text}")
    return parsed


def _rich_text_block(block_type: str, text: str, **extra: Any) -> dict[str, Any]:
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": [{"type": "text", "text": {"content": text}}], **extra},
    }


async def create_page(title: str, content: str, parent_page_id: str | None = None) -> dict[str, Any]:
    """
    Create a Notion page under the target workspace page. `content` may be
    plain text or simple HTML (h1-h3, p, ul/ol/li, b/i) — HTML is converted
    to real Notion blocks (headings/lists) rather than one flat paragraph.
    Returns page_id/url for rollback.
    """
    parent_id = parent_page_id or settings.NOTION_PAGE_ID
    result = await _call_tool(
        "API-post-page",
        {
            "parent": {"page_id": parent_id},
            "properties": {"title": {"title": [{"text": {"content": title}}]}},
            "children": _html_to_blocks(content),
        },
    )
    return {"page_id": result.get("id"), "url": result.get("url"), "title": title}


async def create_action_items(page_id: str, items: list[str]) -> dict[str, Any]:
    """Append an action-item checklist block to an existing page."""
    result = await _call_tool(
        "API-patch-block-children",
        {
            "block_id": page_id,
            "children": [_rich_text_block("to_do", item, checked=False) for item in items],
        },
    )
    return {"page_id": page_id, "items_added": len(items), "block_ids": [b.get("id") for b in result.get("results", [])]}


async def delete_page(page_id: str) -> dict[str, Any]:
    """Rollback: archive a page created earlier in the same run (Notion has no hard delete via API)."""
    await _call_tool("API-patch-page", {"page_id": page_id, "archived": True})
    return {"page_id": page_id, "deleted": True}
