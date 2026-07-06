"""Unified tool registry for the Saiyan Research Agent.

Loads all tools from the ``tools/`` package, builds OpenAI-compatible
tool schemas, and provides call handlers with error handling and logging.

Usage::

    from harness.tool_registry import get_tool_registry
    reg = get_tool_registry()
    schema = reg.list_schemas()   # list of OpenAI tool dicts
    result = reg.call("search_web", {"query": "hello"})
"""

from __future__ import annotations

import json
import logging
from typing import Any

from config import get_config

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Tool schema definitions (standalone — no import of tool implementations)
# ──────────────────────────────────────────────────────────────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information using a search engine.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Fetch and read content from any pasted URL — articles, web pages, GitHub repos, docs, etc.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_x_post",
            "description": "Scrape text from a public X or Twitter URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_linkedin_post",
            "description": "Write a LinkedIn post about a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_substack_post",
            "description": "Write a full long-form Substack newsletter post about a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_substack_note",
            "description": "Write a short Substack newsletter note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_short_note",
            "description": "Write a short bullet-point summary note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_workspace",
            "description": "Search or list Notion pages and databases shared with the integration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "page_size": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_page",
            "description": "Read a Notion page by ID and optionally follow subpages and linked page mentions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string"},
                    "max_depth": {"type": "integer"},
                    "follow_links": {"type": "boolean"},
                },
                "required": ["page_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_root_page",
            "description": "Read everything inside the bot's shared Notion root page.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_workspace",
            "description": "Inspect the shared Notion workspace tree from the root page.",
            "parameters": {
                "type": "object",
                "properties": {"max_depth": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Query rows in any Notion database with optional status filter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string"},
                    "filter_status": {"type": "string"},
                },
                "required": ["database_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_subpage",
            "description": "Create a subpage inside the bot's root write page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_database",
            "description": "Create a database inside the bot's root write page.",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_database",
            "description": "Add a row to a database inside root page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "status": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["database_id", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_page",
            "description": "Append content to any page inside root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["page_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task_list",
            "description": "Create a native Notion to-do/task list page with checkboxes inside the root page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "tasks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "tasks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_calendar_entry",
            "description": "Add a dated entry to a Notion calendar database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string"},
                    "title": {"type": "string"},
                    "date": {"type": "string", "description": "Format: YYYY-MM-DD"},
                    "notes": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["database_id", "title", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "archive_page",
            "description": "Archive a Notion page.",
            "parameters": {
                "type": "object",
                "properties": {"page_id": {"type": "string"}},
                "required": ["page_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "archive_database",
            "description": "Archive a Notion database.",
            "parameters": {
                "type": "object",
                "properties": {"database_id": {"type": "string"}},
                "required": ["database_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_drive_files",
            "description": "List or search files in Google Drive.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_discord_message",
            "description": "Send a message to a different Discord channel by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel_id", "message"],
            },
        },
    },
]


class ToolRegistry:
    """Unified tool registry that maps tool names → callables + schemas."""

    def __init__(self, config=None, block_discord_current_channel: bool = True):
        self._config = config or get_config()
        self._handlers: dict[str, callable] = {}
        self._schemas: list[dict[str, Any]] = list(TOOL_SCHEMAS)
        self._block_discord_current_channel = block_discord_current_channel
        self._current_channel_id: str | None = None
        self._load_tools()

    def _load_tools(self) -> None:
        """Import and register every tool function from the tools/ package."""
        # Import all tool modules once
        from tools.search import search_web  # noqa: F401
        from tools.url_reader import read_url  # noqa: F401
        from tools.x_scraper import scrape_x_post  # noqa: F401
        from tools.content_writer import (  # noqa: F401
            write_linkedin_post,
            write_substack_note,
            write_substack_post,
            write_short_note,
        )
        from tools.notion import (  # noqa: F401
            search_workspace,
            read_page,
            read_root_page,
            inspect_workspace,
            query_database,
            create_subpage,
            create_database,
            add_to_database,
            append_to_page,
            archive_page,
            archive_database,
            create_task_list,
            add_calendar_entry,
        )
        from tools.drive import list_drive_files  # noqa: F401
        from tools.discord_tool import set_bot, send_discord_message  # noqa: F401
        from tools.memory import (  # noqa: F401
            get_history,
            add_message,
            clear_history,
            get_summary,
        )

        # Now build the handler map
        # We need to import from the actual modules to get the callable objects
        import tools.search as _search_mod
        import tools.url_reader as _url_mod
        import tools.x_scraper as _x_mod
        import tools.content_writer as _cw_mod
        import tools.notion as _notion_mod
        import tools.drive as _drive_mod
        import tools.discord_tool as _discord_mod
        import tools.memory as _mem_mod

        handlers = {
            "search_web": lambda a: _search_mod.search_web(a.get("query", "")),
            "read_url": lambda a: _url_mod.read_url(a.get("url", "")),
            "scrape_x_post": lambda a: _x_mod.scrape_x_post(a.get("url", "")),
            "write_linkedin_post": lambda a: _cw_mod.write_linkedin_post(a.get("topic", ""), a.get("context", "")),
            "write_substack_note": lambda a: _cw_mod.write_substack_note(a.get("topic", ""), a.get("context", "")),
            "write_substack_post": lambda a: _cw_mod.write_substack_post(a.get("topic", ""), a.get("context", "")),
            "write_short_note": lambda a: _cw_mod.write_short_note(a.get("topic", ""), a.get("context", "")),
            "search_workspace": lambda a: _notion_mod.search_workspace(a.get("query", ""), a.get("page_size", 20)),
            "read_page": lambda a: _notion_mod.read_page(a.get("page_id", ""), a.get("max_depth", 2), a.get("follow_links", True)),
            "read_root_page": lambda _: _notion_mod.read_root_page(),
            "inspect_workspace": lambda a: _notion_mod.inspect_workspace(a.get("max_depth", 2)),
            "query_database": lambda a: _notion_mod.query_database(a.get("database_id", ""), a.get("filter_status", "")),
            "create_subpage": lambda a: _notion_mod.create_subpage(a.get("title", ""), a.get("content", "")),
            "create_database": lambda a: _notion_mod.create_database(a.get("title", "")),
            "add_to_database": lambda a: _notion_mod.add_to_database(
                a.get("database_id", ""), a.get("title", ""),
                a.get("content", ""), a.get("status", "Todo"), a.get("tags"),
            ),
            "append_to_page": lambda a: _notion_mod.append_to_page(a.get("page_id", ""), a.get("content", "")),
            "create_task_list": lambda a: _notion_mod.create_task_list(a.get("title", ""), a.get("tasks", [])),
            "add_calendar_entry": lambda a: _notion_mod.add_calendar_entry(
                a.get("database_id", ""), a.get("title", ""),
                a.get("date", ""), a.get("notes", ""), a.get("status", "Todo"),
            ),
            "archive_page": lambda a: _notion_mod.archive_page(a.get("page_id", "")),
            "archive_database": lambda a: _notion_mod.archive_database(a.get("database_id", "")),
            "list_drive_files": lambda a: _drive_mod.list_drive_files(a.get("query", "")),
        }

        # Discord message needs special handling
        if self._block_discord_current_channel:
            handlers["send_discord_message"] = lambda a: _discord_mod.send_discord_message(
                a.get("channel_id", ""), a.get("message", ""),
            )
        else:
            handlers["send_discord_message"] = lambda a: _discord_mod.send_discord_message(
                a.get("channel_id", ""), a.get("message", ""),
            )

        self._handlers = handlers

    def set_bot(self, bot) -> None:
        """Set the Discord bot instance for send_discord_message support."""
        import tools.discord_tool as _discord_mod
        _discord_mod.set_bot(bot)

    def set_current_channel(self, channel_id: str) -> None:
        """Set the current channel so send_discord_message can block same-channel replies."""
        self._current_channel_id = channel_id

    def list_schemas(self) -> list[dict[str, Any]]:
        """Return the list of OpenAI-compatible tool schemas."""
        return self._schemas

    def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool by name with the given arguments dict.

        Returns the tool's string result, or an error message if the tool
        is unknown or raised an exception.
        """
        handler = self._handlers.get(tool_name)
        if handler is None:
            return f"Unknown tool: {tool_name}"

        # Discord channel block check
        if tool_name == "send_discord_message" and self._block_discord_current_channel:
            channel_id = str(arguments.get("channel_id", "")).strip()
            if self._current_channel_id and channel_id == self._current_channel_id:
                return "Blocked: cannot send to the current channel. Reply normally instead."

        try:
            result = handler(arguments)
            return str(result)
        except Exception as exc:
            logger.error("Tool %s raised: %s", tool_name, exc, exc_info=True)
            return f"Tool error ({tool_name}): {exc}"

    @property
    def tool_names(self) -> list[str]:
        """Return the list of registered tool names."""
        return list(self._handlers.keys())

    @property
    def handler_count(self) -> int:
        return len(self._handlers)


# Module-level singleton
_tool_registry: ToolRegistry | None = None


def get_tool_registry(config=None, **kwargs) -> ToolRegistry:
    """Return a module-level ToolRegistry singleton."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(config=config, **kwargs)
    return _tool_registry